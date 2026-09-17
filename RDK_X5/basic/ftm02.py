import subprocess
import time


BOARD_ID = 0

# SM-I-001 Analog Input
TEMP_CHANNEL = 1
HUMI_CHANNEL = 2


# User-configured sensor scaling: 0-10 V -> -20..80 degC / 0..100 %RH.
# This setting assumes the connected sensor has a 0-10 V output.
SENSOR_OUTPUT_MAX_V = 10.0
TEMP_MIN_C = -20.0
TEMP_MAX_C = 80.0


def voltage_to_temperature(voltage):
    return TEMP_MIN_C + voltage / SENSOR_OUTPUT_MAX_V * (TEMP_MAX_C - TEMP_MIN_C)


def voltage_to_humidity(voltage):
    return voltage / SENSOR_OUTPUT_MAX_V * 100.0


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
                    f"CH1 Temperature : {temp_voltage:.3f} V ({voltage_to_temperature(temp_voltage):.2f} \u00b0C)    "
                    f"CH2 Humidity : {humi_voltage:.3f} V ({voltage_to_humidity(humi_voltage):.2f} %RH)"
                )

            time.sleep(1)

    except KeyboardInterrupt:

        print("\n프로그램 종료")


if __name__ == "__main__":
    main()