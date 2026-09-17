import time
from smbus2 import SMBus


I2C_BUS = 5
BME280_ADDRESS = 0x76

bus = None
cal = None


def _s16(value):
    return value - 65536 if value & 0x8000 else value


def _read_u16_le(reg):
    data = bus.read_i2c_block_data(BME280_ADDRESS, reg, 2)
    return data[0] | (data[1] << 8)


def _read_s16_le(reg):
    return _s16(_read_u16_le(reg))


def connect():
    global bus, cal

    if bus is not None:
        return

    bus = SMBus(I2C_BUS)

    chip_id = bus.read_byte_data(BME280_ADDRESS, 0xD0)

    if chip_id != 0x60:
        raise RuntimeError(
            f"BME280를 찾을 수 없습니다. CHIP ID = 0x{chip_id:02X}"
        )

    # 보정 계수 읽기
    cal = {}

    cal["T1"] = _read_u16_le(0x88)
    cal["T2"] = _read_s16_le(0x8A)
    cal["T3"] = _read_s16_le(0x8C)

    cal["P1"] = _read_u16_le(0x8E)
    cal["P2"] = _read_s16_le(0x90)
    cal["P3"] = _read_s16_le(0x92)
    cal["P4"] = _read_s16_le(0x94)
    cal["P5"] = _read_s16_le(0x96)
    cal["P6"] = _read_s16_le(0x98)
    cal["P7"] = _read_s16_le(0x9A)
    cal["P8"] = _read_s16_le(0x9C)
    cal["P9"] = _read_s16_le(0x9E)

    cal["H1"] = bus.read_byte_data(BME280_ADDRESS, 0xA1)
    cal["H2"] = _read_s16_le(0xE1)
    cal["H3"] = bus.read_byte_data(BME280_ADDRESS, 0xE3)

    e4 = bus.read_byte_data(BME280_ADDRESS, 0xE4)
    e5 = bus.read_byte_data(BME280_ADDRESS, 0xE5)
    e6 = bus.read_byte_data(BME280_ADDRESS, 0xE6)

    cal["H4"] = _s16((e4 << 4) | (e5 & 0x0F))
    cal["H5"] = _s16((e6 << 4) | (e5 >> 4))

    h6 = bus.read_byte_data(BME280_ADDRESS, 0xE7)
    cal["H6"] = h6 - 256 if h6 > 127 else h6

    # Humidity oversampling x1
    bus.write_byte_data(BME280_ADDRESS, 0xF2, 0x01)

    # Temperature x1 / Pressure x1 / Normal mode
    bus.write_byte_data(BME280_ADDRESS, 0xF4, 0x27)

    # Standby 1000 ms
    bus.write_byte_data(BME280_ADDRESS, 0xF5, 0xA0)


def read():

    try:
        connect()

        data = bus.read_i2c_block_data(
            BME280_ADDRESS,
            0xF7,
            8
        )

        adc_p = (
            (data[0] << 12)
            | (data[1] << 4)
            | (data[2] >> 4)
        )

        adc_t = (
            (data[3] << 12)
            | (data[4] << 4)
            | (data[5] >> 4)
        )

        adc_h = (
            (data[6] << 8)
            | data[7]
        )

        # Temperature
        var1 = (
            adc_t / 16384.0
            - cal["T1"] / 1024.0
        ) * cal["T2"]

        var2 = (
            (
                adc_t / 131072.0
                - cal["T1"] / 8192.0
            ) ** 2
        ) * cal["T3"]

        t_fine = var1 + var2

        temperature = t_fine / 5120.0

        # Pressure
        var1 = t_fine / 2.0 - 64000.0

        var2 = (
            var1 * var1
            * cal["P6"]
            / 32768.0
        )

        var2 += (
            var1
            * cal["P5"]
            * 2.0
        )

        var2 = var2 / 4.0 + cal["P4"] * 65536.0

        var1 = (
            cal["P3"]
            * var1
            * var1
            / 524288.0
            + cal["P2"] * var1
        ) / 524288.0

        var1 = (
            1.0
            + var1 / 32768.0
        ) * cal["P1"]

        if var1 == 0:
            pressure = 0
        else:
            pressure = 1048576.0 - adc_p
            pressure = (
                pressure
                - var2 / 4096.0
            ) * 6250.0 / var1

            var1 = (
                cal["P9"]
                * pressure
                * pressure
                / 2147483648.0
            )

            var2 = (
                pressure
                * cal["P8"]
                / 32768.0
            )

            pressure += (
                var1
                + var2
                + cal["P7"]
            ) / 16.0

        pressure /= 100.0

        # Humidity
        humidity = t_fine - 76800.0

        humidity = (
            adc_h
            - (
                cal["H4"] * 64.0
                + cal["H5"]
                / 16384.0
                * humidity
            )
        ) * (
            cal["H2"]
            / 65536.0
            * (
                1.0
                + cal["H6"]
                / 67108864.0
                * humidity
                * (
                    1.0
                    + cal["H3"]
                    / 67108864.0
                    * humidity
                )
            )
        )

        humidity *= (
            1.0
            - cal["H1"]
            * humidity
            / 524288.0
        )

        humidity = max(
            0.0,
            min(100.0, humidity)
        )

        return {
            "temperature": temperature,
            "humidity": humidity,
            "pressure": pressure
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