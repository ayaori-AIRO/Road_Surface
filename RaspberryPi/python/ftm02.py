import subprocess
import time


BOARD_ID = 0

# 실제 연결
HUMI_CHANNEL = 1
TEMP_CHANNEL = 2


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
            "temperature_voltage": temperature_voltage,
            "humidity": voltage_to_humidity(humidity_voltage),
            "temperature": voltage_to_temperature(temperature_voltage)
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
                    f"Humidity : {data['humidity_voltage']:.3f} V ({data['humidity']:.2f} %RH)    "
                    f"Temperature : {data['temperature_voltage']:.3f} V ({data['temperature']:.2f} \u00b0C)"
                )

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n종료")