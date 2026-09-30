import time
from datetime import datetime

import ct100
import ftm02
import gps
import imu
import bme280

from tcp_client import TCPClient


# ==========================================
# Jetson TCP 설정
# ==========================================

JETSON_IP = "192.168.1.163"   # ← Jetson 실제 IP로 변경
JETSON_PORT = 5000


def main():

    print("==============================================")
    print("          Road Surface Sensor System")
    print("==============================================")

    tcp = TCPClient(
        JETSON_IP,
        JETSON_PORT
    )

    try:

        while True:

            # ==========================================
            # 센서 데이터 읽기
            # ==========================================

            ct_data = ct100.read()
            ftm_data = ftm02.read()
            bme_data = bme280.read()
            gps_data = gps.read()
            imu_data = imu.read()

            now = datetime.now()

            # ==========================================
            # 전송 데이터 생성
            # ==========================================

            sensor_data = {

                "timestamp":
                    now.isoformat(timespec="milliseconds"),

                "ct100":
                    ct_data,

                "ftm02":
                    ftm_data,

                "bme280":
                    bme_data,

                "gps":
                    gps_data,

                "imu":
                    imu_data
            }

            # ==========================================
            # 화면 출력
            # ==========================================

            print()
            print("==============================================")
            print(
                "TIME :",
                now.strftime("%Y-%m-%d %H:%M:%S")
            )
            print("==============================================")

            # CT100
            print("[ CT-100N-CL420 ]")

            if ct_data is not None:

                print(
                    f"Temperature : "
                    f"{ct_data['temperature']:.2f} °C"
                )

                print(
                    f"Current     : "
                    f"{ct_data['current']:.3f} mA"
                )

            else:
                print("No Data")

            print()

            # FTM02
            print("[ BT-FTM02 ]")

            if ftm_data is not None:

                print(
                    f"Humidity Voltage    : "
                    f"{ftm_data['humidity_voltage']:.3f} V  "
                    f"Humidity: {ftm_data['humidity']:.2f} %RH"
                )

                print(
                    f"Temperature Voltage : "
                    f"{ftm_data['temperature_voltage']:.3f} V  "
                    f"Temperature: {ftm_data['temperature']:.2f} \u00b0C"
                )

            else:
                print("No Data")

            print()

            # BME280
            print("[ BME280 ]")

            if bme_data is not None:

                print(
                    f"Temperature : "
                    f"{bme_data['temperature']:.2f} °C"
                )

                print(
                    f"Humidity    : "
                    f"{bme_data['humidity']:.2f} %RH"
                )

                print(
                    f"Pressure    : "
                    f"{bme_data['pressure']:.2f} hPa"
                )

            else:
                print("No Data")

            print()

            # GPS
            print("[ BU-353N GPS ]")

            if gps_data is None:

                print("GPS 데이터 수신 없음")

            elif not gps_data["fix"]:

                print("GPS Fix 없음")

                print(
                    f"Satellites : "
                    f"{gps_data['satellites']}"
                )

                print(
                    f"Quality    : "
                    f"{gps_data['quality']}"
                )

            else:

                print(
                    f"Latitude   : "
                    f"{gps_data['latitude']:.6f}"
                )

                print(
                    f"Longitude  : "
                    f"{gps_data['longitude']:.6f}"
                )

                print(
                    f"Altitude   : "
                    f"{gps_data['altitude']:.1f} m"
                )

                print(
                    f"Satellites : "
                    f"{gps_data['satellites']}"
                )

                print(
                    f"Quality    : "
                    f"{gps_data['quality']}"
                )

            print()

            # IMU
            print("[ WT901C485 IMU ]")

            if imu_data is not None:

                print(
                    "ACC   : "
                    f"X={imu_data['acc']['x']:.3f} "
                    f"Y={imu_data['acc']['y']:.3f} "
                    f"Z={imu_data['acc']['z']:.3f} m/s²"
                )

                print(
                    "GYRO  : "
                    f"X={imu_data['gyro']['x']:.2f} "
                    f"Y={imu_data['gyro']['y']:.2f} "
                    f"Z={imu_data['gyro']['z']:.2f} °/s"
                )

                print(
                    "ANGLE : "
                    f"Roll={imu_data['angle']['roll']:.2f}° "
                    f"Pitch={imu_data['angle']['pitch']:.2f}° "
                    f"Yaw={imu_data['angle']['yaw']:.2f}°"
                )

            else:
                print("No Data")

            # ==========================================
            # Jetson으로 TCP 전송
            # ==========================================

            if tcp.send(sensor_data):

                print()
                print("[TCP] Sensor Data 전송 완료")

            else:

                print()
                print("[TCP] Sensor Data 전송 실패")

            print("==============================================")

            time.sleep(1)

    except KeyboardInterrupt:

        print("\n프로그램 종료")

    finally:

        tcp.close()

        gps.close()
        imu.close()


if __name__ == "__main__":
    main()