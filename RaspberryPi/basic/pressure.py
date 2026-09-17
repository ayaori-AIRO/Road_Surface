import time
import board
import adafruit_bme280.basic as adafruit_bme280

# Raspberry Pi 기본 I2C
i2c = board.I2C()

# BME280 주소
# 보통 0x76 또는 0x77
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)

print("BME280 연결 성공")
print("------------------------")

while True:
    print(f"온도 : {bme280.temperature:.2f} °C")
    print(f"습도 : {bme280.relative_humidity:.2f} %")
    print(f"기압 : {bme280.pressure:.2f} hPa")
    print("------------------------")

    time.sleep(1)