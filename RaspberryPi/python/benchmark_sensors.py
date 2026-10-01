"""TCP 없이 센서 수집 시간과 데이터를 출력합니다.

실행: python3 RaspberryPi/benchmark_sensors.py
첫 회에는 연결/초기화 시간이 포함됩니다.
화면 출력 및 반복 사이 1초 대기는 측정에서 제외됩니다.
기존 read() 내부의 오류 처리 시간은 포함됩니다.
"""

import time
from datetime import datetime

import RaspberryPi.python.ct100 as ct100
import RaspberryPi.python.ftm02 as ftm02
import RaspberryPi.python.bme280 as bme280
import RaspberryPi.python.gps as gps
import RaspberryPi.python.imu as imu


def collect():
    """main과 같은 순서로 센서를 읽고 데이터와 소요 시간(ms)을 반환합니다."""
    start = time.perf_counter_ns()
    ct_data = ct100.read()
    t1 = time.perf_counter_ns()
    ftm_data = ftm02.read()
    t2 = time.perf_counter_ns()
    bme_data = bme280.read()
    t3 = time.perf_counter_ns()
    gps_data = gps.read()
    t4 = time.perf_counter_ns()
    imu_data = imu.read()
    end = time.perf_counter_ns()
    data = (ct_data, ftm_data, bme_data, gps_data, imu_data)
    durations = (t1 - start, t2 - t1, t3 - t2, t4 - t3, end - t4, end - start)
    return data, [duration / 1_000_000 for duration in durations]


def print_data(data):
    ct_data, ftm_data, bme_data, gps_data, imu_data = data
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


def main():
    iteration = 0
    print("센서 수집 시간 측정 (TCP 없음)")
    print("화면 출력 및 1초 대기 제외 / Ctrl+C로 종료")
    try:
        while True:
            data, timings = collect()
            iteration += 1
            print("\n==============================================")
            print(f"TIME : {datetime.now():%Y-%m-%d %H:%M:%S} / 측정 {iteration}회")
            if iteration == 1:
                print("첫 회: 센서 연결 및 초기화 시간 포함")
            print("==============================================")
            print("[ 수집 시간 ]")
            for name, elapsed, value in zip(
                ("CT100", "FTM02", "BME280", "GPS", "IMU"), timings, data
            ):
                status = "수신 성공" if value is not None else "수집 실패 (None)"
                if name == "GPS" and value is not None and not value["fix"]:
                    status = "수신 성공 / Fix 없음"
                print(f"{name:6} : {elapsed:10.3f} ms | {status}")
            print(f"전체 수집 시간 : {timings[-1]:.3f} ms ({timings[-1] / 1000:.6f} 초)")
            if any(value is None for value in data):
                print("일부 센서 수집 실패: 전체 시간에 실패 처리/대기가 포함됩니다.")
            print("\n[ 센서 데이터 ]")
            print_data(data)
            print("==============================================")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n측정 종료")
    finally:
        try:
            gps.close()
        finally:
            imu.close()


if __name__ == "__main__":
    main()
