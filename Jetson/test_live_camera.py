import threading
import time
import unittest
from types import SimpleNamespace

from Jetson.live_camera import CameraStream


class LatestFrameTests(unittest.TestCase):
    def test_slow_encoder_skips_replaced_frames(self):
        stream = CameraStream('101', 'h264')
        pending = {'condition': threading.Condition(), 'frame': ('first', time.monotonic())}
        finished = threading.Event()
        started = threading.Event()
        release = threading.Event()
        latest_encoded = threading.Event()
        encoded = []

        def encode(extension, frame, options):
            encoded.append(frame)
            if frame == 'first':
                started.set()
                release.wait(2)
            if frame == 'latest':
                latest_encoded.set()
            return True, SimpleNamespace(tobytes=lambda: frame.encode())

        cv2 = SimpleNamespace(imencode=encode, IMWRITE_JPEG_QUALITY=1)
        worker = threading.Thread(target=stream._encode_latest, args=(cv2, pending, finished))
        worker.start()
        try:
            self.assertTrue(started.wait(2))
            with pending['condition']:
                pending['frame'] = ('old', time.monotonic())
                pending['frame'] = ('latest', time.monotonic())
                pending['condition'].notify()
            release.set()
            self.assertTrue(latest_encoded.wait(2))
        finally:
            release.set()
            finished.set()
            with pending['condition']:
                pending['condition'].notify_all()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(encoded, ['first', 'latest'])


if __name__ == '__main__':
    unittest.main()
