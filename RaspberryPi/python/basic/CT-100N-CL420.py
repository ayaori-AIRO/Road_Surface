import subprocess
import time


BOARD_ID = 0
CURRENT_CHANNEL = 1

# CT-100N-CL420 측정 범위
TEMP_MIN = -20.0     # °C
TEMP_MAX = 100.0     # °C

CURRENT_MIN = 4.0    # mA
CURRENT_MAX = 20.0   # mA


def read_current(channel):
    """
    SM-I-001의 4~20mA Analog Input 전류 읽기
    """
    try:
        result = subprocess.run(
            [
                "megaind",
                str(BOARD_ID),
                "iinrd",
                str(channel)
            ],
            capture_output=True,
            text=True,
            timeout=2
        )

        if result.returncode != 0:
            print(f"CH{channel} 읽기 실패:")
            print(result.stderr)
            return None

        return float(result.stdout.strip())

    except Exception as e:
        print(f"CH{channel} 오류: {e}")
        return None


def current_to_temperature(current):
    """
    4~20mA -> -20~100°C 변환
    """

    temperature = TEMP_MIN + (
        (current - CURRENT_MIN)
        / (CURRENT_MAX - CURRENT_MIN)
        * (TEMP_MAX - TEMP_MIN)
    )

    return temperature


def main():

    print("====================================")
    print("CT-100N-CL420 + SM-I-001")
    print(f"CH{CURRENT_CHANNEL} : Temperature")
    print("4~20mA -> -20~100 °C")
    print("====================================")

    try:

        while True:

            current = read_current(CURRENT_CHANNEL)

            if current is not None:

                temperature = current_to_temperature(current)

                print(
                    f"Current : {current:6.3f} mA    "
                    f"Temperature : {temperature:6.2f} °C"
                )

            time.sleep(1)

    except KeyboardInterrupt:

        print("\n프로그램 종료")


if __name__ == "__main__":
    main()