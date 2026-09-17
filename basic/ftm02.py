import subprocess
import time


BOARD_ID = 0

# SM-I-001 Analog Input
TEMP_CHANNEL = 1
HUMI_CHANNEL = 2


def read_voltage(channel):
    """
    SM-I-001의 0~10V Analog Input 전압 읽기
    """
    try:
        result = subprocess.run(
            [
                "megaind",
                str(BOARD_ID),
                "uinrd",
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

        voltage = float(result.stdout.strip())

        return voltage

    except Exception as e:
        print(f"CH{channel} 오류: {e}")
        return None


def main():

    print("====================================")
    print("FTM02 + SM-I-001")
    print("CH1 : Temperature Output")
    print("CH2 : Humidity Output")
    print("====================================")

    try:

        while True:

            temp_voltage = read_voltage(TEMP_CHANNEL)
            humi_voltage = read_voltage(HUMI_CHANNEL)

            if temp_voltage is not None and humi_voltage is not None:

                print(
                    f"CH1 Temperature : {temp_voltage:.3f} V    "
                    f"CH2 Humidity : {humi_voltage:.3f} V"
                )

            time.sleep(1)

    except KeyboardInterrupt:

        print("\n프로그램 종료")


if __name__ == "__main__":
    main()