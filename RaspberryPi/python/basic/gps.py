import serial
import pynmea2
import time

# BU-353N GPS 설정
GPS_PORT = "/dev/ttyUSB1"
BAUD_RATE = 4800

def main():
    try:
        gps = serial.Serial(
            port=GPS_PORT,
            baudrate=BAUD_RATE,
            timeout=1
        )

        print(f"GPS 연결 성공: {GPS_PORT}")
        print("GPS 데이터 수신 중...\n")

        while True:
            try:
                line = gps.readline().decode(
                    "ascii",
                    errors="ignore"
                ).strip()

                if not line:
                    continue

                # 원본 NMEA 데이터
                print("RAW:", line)

                # GGA 메시지
                # 위치, 고도, 위성 수 등의 정보가 들어있음
                if line.startswith("$GPGGA") or line.startswith("$GNGGA"):

                    msg = pynmea2.parse(line)

                    latitude = msg.latitude
                    longitude = msg.longitude
                    altitude = msg.altitude
                    satellites = msg.num_sats
                    gps_quality = msg.gps_qual

                    print("----- GPS 정보 -----")
                    print(f"위도       : {latitude}")
                    print(f"경도       : {longitude}")
                    print(f"고도       : {altitude} m")
                    print(f"위성 수    : {satellites}")
                    print(f"GPS Quality: {gps_quality}")
                    print("--------------------\n")

            except pynmea2.ParseError:
                pass

            except UnicodeDecodeError:
                pass

            time.sleep(0.01)

    except serial.SerialException as e:
        print("GPS 연결 실패")
        print(e)


if __name__ == "__main__":
    main()