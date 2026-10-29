"""Lazy, shared Hikvision capture workers for browser JPEG previews."""
import threading
import time


class CameraStream:
    def __init__(self, channel, codec):
        self.channel = channel
        self.codec = codec
        self.lock = threading.Lock()
        self.thread = None
        self.jpeg = None
        self.updated = 0
        self.requested = 0
        self.stop_event = threading.Event()

    def _encode_latest(self, cv2, pending, finished):
        """Encode a single replaceable slot; never queue old camera frames."""
        while not finished.is_set():
            with pending['condition']:
                pending['condition'].wait_for(lambda: pending['frame'] is not None or finished.is_set())
                if finished.is_set():
                    return
                frame, captured_at = pending['frame']
                pending['frame'] = None
            try:
                ok, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok and not finished.is_set():
                    with self.lock:
                        self.jpeg = jpeg.tobytes()
                        self.updated = captured_at
            except Exception:
                # A bad frame must not terminate camera reception.
                continue

    def frame(self):
        with self.lock:
            self.requested = time.monotonic()
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._run, daemon=True)
                self.thread.start()
            return self.jpeg if time.monotonic() - self.updated < 3 else None

    def _run(self):
        # Import only when the live tab is opened; telemetry works without OpenCV.
        try:
            try:
                from . import HIKtest as hik
            except ImportError:
                import HIKtest as hik
            cv2 = hik.cv2
            visible = self.channel == '101'
            url = hik.make_rtsp_url(hik.VISIBLE_CHANNEL if visible else hik.THERMAL_CHANNEL)
            codec = hik.VISIBLE_CODEC if visible else hik.THERMAL_CODEC
            while not self.stop_event.is_set():
                with self.lock:
                    if time.monotonic() - self.requested > 10:
                        return
                capture = None
                encoder = None
                finished = threading.Event()
                pending = {'condition': threading.Condition(), 'frame': None}
                try:
                    pipeline = hik.make_gstreamer_pipeline(url, codec)
                    capture = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER,
                                              [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                                               cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000])
                    if not capture.isOpened():
                        capture.release()
                        capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG,
                                                  [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                                                   cv2.CAP_PROP_READ_TIMEOUT_MSEC, 3000])
                        backend = 'FFmpeg'
                    else:
                        backend = 'GStreamer/NVIDIA'
                    if capture.isOpened():
                        print(f'[camera {self.channel}] Connected: {backend}', flush=True)
                        encoder = threading.Thread(target=self._encode_latest,
                                                   args=(cv2, pending, finished), daemon=True)
                        encoder.start()
                    while capture.isOpened() and not self.stop_event.is_set():
                        with self.lock:
                            if time.monotonic() - self.requested > 10:
                                return
                        ok, frame = capture.read()
                        if not ok:
                            break
                        with pending['condition']:
                            pending['frame'] = (frame, time.monotonic())
                            pending['condition'].notify()
                except Exception:
                    # Never expose camera credentials in HTTP errors or logs.
                    pass
                finally:
                    finished.set()
                    with pending['condition']:
                        pending['condition'].notify_all()
                    if encoder is not None:
                        encoder.join()
                    if capture is not None:
                        capture.release()
                    with self.lock:
                        self.jpeg = None
                self.stop_event.wait(2)
        except Exception:
            # Missing camera dependencies must not stop the telemetry server.
            return


class LiveCameras:
    def __init__(self):
        self.streams = {
            'visible': CameraStream('101', 'h264'),
            'thermal': CameraStream('201', 'h264'),
        }

    def close(self):
        for stream in self.streams.values():
            stream.stop_event.set()
