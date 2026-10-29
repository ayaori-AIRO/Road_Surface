import sys

# --------------------------------------------------
# Jetson 시스템 OpenCV를 pip OpenCV보다 먼저 사용
# GStreamer가 활성화된 OpenCV 경로
# --------------------------------------------------
SYSTEM_OPENCV_PATH = "/usr/lib/python3/dist-packages"

if SYSTEM_OPENCV_PATH in sys.path:
    sys.path.remove(SYSTEM_OPENCV_PATH)

sys.path.insert(0, SYSTEM_OPENCV_PATH)

import threading
import time

import cv2
import numpy as np


# ==================================================
# 카메라 설정
# ==================================================

CAMERA_IP = "192.168.0.64"
CAMERA_USER = "admin"
CAMERA_PASSWORD = "unieye55"

RTSP_PORT = 554

# Hikvision 채널
VISIBLE_CHANNEL = "101"
THERMAL_CHANNEL = "201"

# 카메라 코덱
# H.264이면 "h264"
# H.265이면 "h265"
VISIBLE_CODEC = "h264"
THERMAL_CODEC = "h264"

# GStreamer RTSP 버퍼 시간(ms)
# 너무 낮으면 끊김이 발생할 수 있습니다.
RTSP_LATENCY = 50


def make_rtsp_url(channel):
    return (
        f"rtsp://{CAMERA_USER}:{CAMERA_PASSWORD}"
        f"@{CAMERA_IP}:{RTSP_PORT}"
        f"/Streaming/Channels/{channel}"
    )


def make_gstreamer_pipeline(url, codec):
    if codec.lower() == "h265":
        depay = "rtph265depay"
        parser = "h265parse"
    else:
        depay = "rtph264depay"
        parser = "h264parse"

    pipeline = (
        f'rtspsrc location="{url}" '
        f"protocols=tcp "
        f"latency={RTSP_LATENCY} "
        f"drop-on-latency=true ! "
        f"{depay} ! "
        f"{parser} ! "
        f"nvv4l2decoder enable-max-performance=1 ! "
        f"nvvidconv ! "
        f"video/x-raw,format=BGRx ! "
        f"videoconvert ! "
        f"video/x-raw,format=BGR ! "
        f"appsink "
        f"drop=true "
        f"max-buffers=1 "
        f"sync=false"
    )

    return pipeline


class LatestFrameCapture:
    """
    RTSP 영상을 별도 스레드에서 계속 읽고
    가장 최신 프레임 한 장만 보관합니다.
    """

    def __init__(self, name, url, codec):
        self.name = name
        self.url = url
        self.codec = codec

        self.capture = None
        self.backend = None

        self.frame = None
        self.frame_number = 0
        self.lock = threading.Lock()

        self.stop_event = threading.Event()
        self.thread = None

    def open(self):
        pipeline = make_gstreamer_pipeline(
            self.url,
            self.codec,
        )

        print(f"{self.name} GStreamer 연결 시도")
        print(pipeline)

        capture = cv2.VideoCapture(
            pipeline,
            cv2.CAP_GSTREAMER,
        )

        if capture.isOpened():
            self.capture = capture
            self.backend = "GStreamer/NVIDIA"

        else:
            capture.release()

            print(
                f"{self.name}: GStreamer 연결 실패, "
                "FFmpeg로 전환합니다."
            )

            capture = cv2.VideoCapture(
                self.url,
                cv2.CAP_FFMPEG,
            )

            capture.set(
                cv2.CAP_PROP_BUFFERSIZE,
                1,
            )

            if not capture.isOpened():
                capture.release()

                raise RuntimeError(
                    f"{self.name} RTSP 연결 실패"
                )

            self.capture = capture
            self.backend = "FFmpeg"

        self.thread = threading.Thread(
            target=self._reader_loop,
            name=f"{self.name}-reader",
            daemon=True,
        )

        self.thread.start()

        print(
            f"{self.name} 연결 성공: "
            f"{self.backend}"
        )

    def _reader_loop(self):
        failure_count = 0

        while not self.stop_event.is_set():
            if self.capture is None:
                break

            ok, frame = self.capture.read()

            if not ok:
                failure_count += 1

                if (
                    failure_count == 1
                    or failure_count % 100 == 0
                ):
                    print(
                        f"{self.name}: "
                        "프레임 수신 대기 중"
                    )

                time.sleep(0.01)
                continue

            failure_count = 0

            with self.lock:
                # 이전 프레임은 버리고
                # 항상 최신 프레임으로 교체합니다.
                self.frame = frame
                self.frame_number += 1

    def get_latest(self):
        with self.lock:
            if self.frame is None:
                return None, self.frame_number

            return (
                self.frame.copy(),
                self.frame_number,
            )

    def close(self):
        self.stop_event.set()

        if self.capture is not None:
            self.capture.release()
            self.capture = None

        if self.thread is not None:
            self.thread.join(timeout=1.0)
            self.thread = None


def resize_to_height(frame, target_height):
    original_height = frame.shape[0]
    original_width = frame.shape[1]

    target_width = int(
        original_width
        * target_height
        / original_height
    )

    return cv2.resize(
        frame,
        (target_width, target_height),
        interpolation=cv2.INTER_LINEAR,
    )


def add_title(frame, title):
    cv2.rectangle(
        frame,
        (0, 0),
        (frame.shape[1], 60),
        (0, 0, 0),
        thickness=-1,
    )

    cv2.putText(
        frame,
        title,
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (0, 255, 0),
        2,
        cv2.LINE_AA,
    )


def main():
    print("=" * 60)
    print("Hikvision Jetson 저지연 라이브뷰")
    print("=" * 60)

    print("OpenCV 버전:", cv2.__version__)
    print("OpenCV 위치:", cv2.__file__)

    gstreamer_enabled = (
        "GStreamer:                   YES"
        in cv2.getBuildInformation()
    )

    print(
        "OpenCV GStreamer:",
        "YES" if gstreamer_enabled else "NO",
    )

    if not gstreamer_enabled:
        raise RuntimeError(
            "현재 OpenCV는 GStreamer를 지원하지 않습니다.\n"
            "OpenCV 위치를 확인하세요:\n"
            f"{cv2.__file__}"
        )

    visible_url = make_rtsp_url(
        VISIBLE_CHANNEL,
    )

    thermal_url = make_rtsp_url(
        THERMAL_CHANNEL,
    )

    visible_capture = LatestFrameCapture(
        name="가시광",
        url=visible_url,
        codec=VISIBLE_CODEC,
    )

    thermal_capture = LatestFrameCapture(
        name="열화상",
        url=thermal_url,
        codec=THERMAL_CODEC,
    )

    try:
        visible_capture.open()
        thermal_capture.open()

        print("=" * 60)
        print("라이브 화면 시작")
        print("종료: ESC 또는 Q")
        print("=" * 60)

        visible_frame = None
        thermal_frame = None

        last_visible_number = -1
        last_thermal_number = -1

        while True:
            new_visible, visible_number = (
                visible_capture.get_latest()
            )

            new_thermal, thermal_number = (
                thermal_capture.get_latest()
            )

            if (
                new_visible is not None
                and visible_number
                != last_visible_number
            ):
                visible_frame = new_visible
                last_visible_number = (
                    visible_number
                )

            if (
                new_thermal is not None
                and thermal_number
                != last_thermal_number
            ):
                thermal_frame = new_thermal
                last_thermal_number = (
                    thermal_number
                )

            if (
                visible_frame is None
                or thermal_frame is None
            ):
                key = cv2.waitKey(1) & 0xFF

                if key in (27, ord("q")):
                    break

                time.sleep(0.005)
                continue

            target_height = min(
                visible_frame.shape[0],
                thermal_frame.shape[0],
            )

            visible_display = resize_to_height(
                visible_frame,
                target_height,
            )

            thermal_display = resize_to_height(
                thermal_frame,
                target_height,
            )

            add_title(
                visible_display,
                (
                    "Visible - "
                    f"{visible_capture.backend}"
                ),
            )

            add_title(
                thermal_display,
                (
                    "Thermal - "
                    f"{thermal_capture.backend}"
                ),
            )

            combined = np.hstack(
                (
                    visible_display,
                    thermal_display,
                )
            )

            cv2.imshow(
                "Visible | Thermal - Low Latency",
                combined,
            )

            key = cv2.waitKey(1) & 0xFF

            if key in (27, ord("q")):
                break

    except KeyboardInterrupt:
        print("사용자가 프로그램을 중지했습니다.")

    finally:
        print("카메라 연결 종료 중")

        visible_capture.close()
        thermal_capture.close()

        cv2.destroyAllWindows()

        print("프로그램 종료")


if __name__ == "__main__":
    main()