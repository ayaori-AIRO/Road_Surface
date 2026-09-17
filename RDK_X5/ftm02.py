import subprocess
import time


BOARD_ID = 0

# 실제 연결
HUMI_CHANNEL = 1
TEMP_CHANNEL = 2


def read_voltage(channel):
    """SM-I-001의 0~10V 입력 읽기"""

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
        raise RuntimeError(result.stderr.strip())

    return float(result.stdout.strip())


def read():
    """FTM02 데이터 한 번 읽기"""

    try:

        humidity_voltage = read_voltage(HUMI_CHANNEL)
        temperature_voltage = read_voltage(TEMP_CHANNEL)

        return {
            "humidity_voltage": humidity_voltage,
            "temperature_voltage": temperature_voltage
        }

    except Exception as e:
        print(f"[FTM02 ERROR] {e}")
        return None


if __name__ == "__main__":

    print("BT-FTM02 Test")
    print("CH1 = Humidity")
    print("CH2 = Temperature")
    print("------------------------------")

    try:

        while True:

            data = read()

            if data is not None:

                print(
                    f"Humidity : {data['humidity_voltage']:.3f} V    "
                    f"Temperature : {data['temperature_voltage']:.3f} V"
                )

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n종료")