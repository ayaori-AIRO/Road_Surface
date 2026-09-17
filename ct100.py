import subprocess
import time


BOARD_ID = 0
CURRENT_CHANNEL = 1

# CT-100N-CL420 측정 범위
TEMP_MIN = -20.0
TEMP_MAX = 100.0

CURRENT_MIN = 4.0
CURRENT_MAX = 20.0


def read_current():
    """SM-I-001의 4~20mA 입력 읽기"""

    result = subprocess.run(
        [
            "megaind",
            str(BOARD_ID),
            "iinrd",
            str(CURRENT_CHANNEL)
        ],
        capture_output=True,
        text=True,
        timeout=2
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    return float(result.stdout.strip())


def current_to_temperature(current):
    """4~20mA → -20~100°C 변환"""

    return TEMP_MIN + (
        (current - CURRENT_MIN)
        / (CURRENT_MAX - CURRENT_MIN)
        * (TEMP_MAX - TEMP_MIN)
    )


def read():
    """현재 CT100 데이터 한 번 읽기"""

    try:
        current = read_current()
        temperature = current_to_temperature(current)

        return {
            "current": current,
            "temperature": temperature
        }

    except Exception as e:
        print(f"[CT100 ERROR] {e}")
        return None


if __name__ == "__main__":

    print("CT-100N-CL420 Test")
    print("------------------------------")

    try:
        while True:

            data = read()

            if data is not None:
                print(
                    f"Current : {data['current']:.3f} mA    "
                    f"Temperature : {data['temperature']:.2f} °C"
                )

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n종료")