import serial
import pynmea2
import time


# ==========================================
# BU-353N GPS 설정
# ==========================================

GPS_PORT = "/dev/ttyUSB0"
BAUD_RATE = 4800

gps_serial = None


def connect():
    """
    GPS 시리얼 포트 연결
    """

    global gps_serial

    if gps_serial is None or not gps_serial.is_open:

        gps_serial = serial.Serial(
            port=GPS_PORT,
            baudrate=BAUD_RATE,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=0.2
        )


def read(timeout=1.0):
    """
    BU-353N GPS에서 GGA 데이터 한 번 읽기

    성공:
    {
        "latitude": 위도,
        "longitude": 경도,
        "altitude": 고도(m),
        "satellites": 위성 수,
        "quality": GPS Fix Quality
    }

    GPS Fix가 없거나 데이터를 받지 못하면 None
    """

    try:

        connect()

        start_time = time.time()

        while time.time() - start_time < timeout:

            line = gps_serial.readline().decode(
                "ascii",
                errors="ignore"
            ).strip()

            if not line:
                continue

            # GGA 메시지만 사용
            if (
                line.startswith("$GPGGA")
                or line.startswith("$GNGGA")
            ):

                try:

                    msg = pynmea2.parse(line)

                    quality = int(msg.gps_qual or 0)
                    satellites = int(msg.num_sats or 0)

                    # GPS 위치 Fix가 아직 안 된 상태
                    if quality == 0:

                        return {
                            "fix": False,
                            "latitude": None,
                            "longitude": None,
                            "altitude": None,
                            "satellites": satellites,
                            "quality": quality
                        }

                    return {
                        "fix": True,
                        "latitude": msg.latitude,
                        "longitude": msg.longitude,
                        "altitude": float(msg.altitude or 0),
                        "satellites": satellites,
                        "quality": quality
                    }

                except pynmea2.ParseError:
                    continue

                except (ValueError, TypeError):
                    continue

        # GGA 메시지 자체를 못 받은 경우
        return None

    except serial.SerialException as e:

        print(f"[GPS SERIAL ERROR] {e}")
        return None

    except Exception as e:

        print(f"[GPS ERROR] {e}")
        return None


def close():
    """
    GPS 시리얼 포트 종료
    """

    global gps_serial

    if gps_serial is not None:

        if gps_serial.is_open:
            gps_serial.close()

        gps_serial = None


# ==========================================
# 단독 실행 테스트
# ==========================================

if __name__ == "__main__":

    print("========================================")
    print("BU-353N GPS Test")
    print(f"PORT : {GPS_PORT}")
    print(f"BAUD : {BAUD_RATE}")
    print("========================================")

    try:

        while True:

            data = read()

            if data is None:

                print("GPS 데이터 수신 없음")

            elif not data["fix"]:

                print(
                    f"GPS Fix 없음    "
                    f"Satellites : {data['satellites']}    "
                    f"Quality : {data['quality']}"
                )

            else:

                print(
                    f"LAT : {data['latitude']:.6f}    "
                    f"LON : {data['longitude']:.6f}    "
                    f"ALT : {data['altitude']:.1f} m    "
                    f"SAT : {data['satellites']}    "
                    f"QUALITY : {data['quality']}"
                )

            time.sleep(1)

    except KeyboardInterrupt:

        print("\n프로그램 종료")

    finally:

        close()