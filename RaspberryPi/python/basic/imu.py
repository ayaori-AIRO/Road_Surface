import serial
import time
import struct

# ==========================================
# WT901C485 설정
# ==========================================
PORT = "/dev/ttyUSB0"   # ls /dev/ttyUSB* 로 확인
BAUDRATE = 9600
SLAVE_ID = 0x50

# 중력가속도
G = 9.80665


def modbus_crc(data):
    """Modbus RTU CRC16 계산"""
    crc = 0xFFFF

    for byte in data:
        crc ^= byte

        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1

    return crc


def make_read_command(slave_id, start_register, count):
    """Modbus Function 0x03 명령 생성"""

    command = bytearray([
        slave_id,
        0x03,
        (start_register >> 8) & 0xFF,
        start_register & 0xFF,
        (count >> 8) & 0xFF,
        count & 0xFF
    ])

    crc = modbus_crc(command)

    # Modbus CRC는 Low Byte 먼저
    command.append(crc & 0xFF)
    command.append((crc >> 8) & 0xFF)

    return command


def int16(high, low):
    """2바이트를 signed int16으로 변환"""
    return struct.unpack(">h", bytes([high, low]))[0]


def read_imu(ser):
    # WT901C485 데이터 영역
    # 0x003A부터 13개 레지스터 읽기
    command = make_read_command(
        SLAVE_ID,
        0x003A,
        13
    )

    ser.reset_input_buffer()

    ser.write(command)
    ser.flush()

    # 응답:
    # ID + Function + ByteCount + 26 data bytes + CRC 2
    response = ser.read(31)

    if len(response) != 31:
        print(f"❌ 응답 길이 오류: {len(response)} bytes")
        if response:
            print("RX:", response.hex(" "))
        return None

    # 기본 응답 확인
    if response[0] != SLAVE_ID:
        print("❌ Slave ID 불일치")
        return None

    if response[1] != 0x03:
        print("❌ Modbus Function 불일치")
        return None

    if response[2] != 26:
        print("❌ 데이터 길이 불일치")
        return None

    # CRC 확인
    received_crc = response[-2] | (response[-1] << 8)
    calculated_crc = modbus_crc(response[:-2])

    if received_crc != calculated_crc:
        print("❌ CRC 오류")
        return None

    data = response[3:-2]

    # ==========================================
    # 센서값 변환
    # ==========================================

    ax_raw = int16(data[0], data[1])
    ay_raw = int16(data[2], data[3])
    az_raw = int16(data[4], data[5])

    gx_raw = int16(data[6], data[7])
    gy_raw = int16(data[8], data[9])
    gz_raw = int16(data[10], data[11])

    roll_raw  = int16(data[12], data[13])
    pitch_raw = int16(data[14], data[15])
    yaw_raw   = int16(data[16], data[17])

    # 가속도
    # ±16 g
    ax_g = ax_raw / 32768.0 * 16
    ay_g = ay_raw / 32768.0 * 16
    az_g = az_raw / 32768.0 * 16

    ax_ms2 = ax_g * G
    ay_ms2 = ay_g * G
    az_ms2 = az_g * G

    # 각속도
    # ±2000 °/s
    gx = gx_raw / 32768.0 * 2000
    gy = gy_raw / 32768.0 * 2000
    gz = gz_raw / 32768.0 * 2000

    # 각도
    # ±180°
    roll  = roll_raw  / 32768.0 * 180
    pitch = pitch_raw / 32768.0 * 180
    yaw   = yaw_raw   / 32768.0 * 180

    return {
        "acc_g": (ax_g, ay_g, az_g),
        "acc_ms2": (ax_ms2, ay_ms2, az_ms2),

        "gyro": (gx, gy, gz),

        "angle": (roll, pitch, yaw)
    }


# ==========================================
# MAIN
# ==========================================

print("========================================")
print("WT901C485 USB-RS485")
print(f"PORT : {PORT}")
print(f"BAUD : {BAUDRATE}")
print(f"ID   : 0x{SLAVE_ID:02X}")
print("========================================")

try:
    ser = serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        bytesize=8,
        parity=serial.PARITY_NONE,
        stopbits=1,
        timeout=0.5
    )

except serial.SerialException as e:
    print("❌ Serial Port Open 실패")
    print(e)
    exit()


try:

    while True:

        result = read_imu(ser)

        if result is not None:

            ax, ay, az = result["acc_ms2"]
            gx, gy, gz = result["gyro"]
            roll, pitch, yaw = result["angle"]

            print(
                f"ACC  "
                f"X:{ax:8.3f}  "
                f"Y:{ay:8.3f}  "
                f"Z:{az:8.3f} m/s²"
            )

            print(
                f"GYRO "
                f"X:{gx:8.2f}  "
                f"Y:{gy:8.2f}  "
                f"Z:{gz:8.2f} °/s"
            )

            print(
                f"ANGLE "
                f"Roll:{roll:7.2f}°  "
                f"Pitch:{pitch:7.2f}°  "
                f"Yaw:{yaw:7.2f}°"
            )

            print("-" * 70)

        time.sleep(0.1)


except KeyboardInterrupt:

    print("\n종료합니다.")


finally:

    ser.close()