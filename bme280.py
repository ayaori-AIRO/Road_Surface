import time
import board
import adafruit_bme280.basic as adafruit_bme280


bme280_sensor = None


def connect():

    global bme280_sensor

    if bme280_sensor is None:

        i2c = board.I2C()

        bme280_sensor = adafruit_bme280.Adafruit_BME280_I2C(
            i2c,
            address=0x76
        )


def read():

    try:

        connect()

        return {
            "temperature": bme280_sensor.temperature,
            "humidity": bme280_sensor.relative_humidity,
            "pressure": bme280_sensor.pressure
        }

    except Exception as e:

        print(f"[BME280 ERROR] {e}")
        return None


if __name__ == "__main__":

    print("BME280 Test")
    print("------------------------------")

    try:

        while True:

            data = read()

            if data is not None:

                print(
                    f"Temperature : {data['temperature']:.2f} °C    "
                    f"Humidity : {data['humidity']:.2f} %RH    "
                    f"Pressure : {data['pressure']:.2f} hPa"
                )

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n종료")