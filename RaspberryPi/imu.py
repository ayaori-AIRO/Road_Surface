import serial
import struct
import time


PORT = "/dev/ttyUSB1"
BAUDRATE = 9600
SLAVE_ID = 0x50

G = 9.80665

imu_serial = None


def modbus_crc(data):

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

    command = bytearray([
        slave_id,
        0x03,
        (start_register >> 8) & 0xFF,
        start_register & 0xFF,
        (count >> 8) & 0xFF,
        count & 0xFF
    ])

    crc = modbus_crc(command)

    command.append(crc & 0xFF)
    command.append((crc >> 8) & 0xFF)

    return command


def int16(high, low):

    return struct.unpack(
        ">h",
        bytes([high, low])
    )[0]


def connect():

    global imu_serial

    if imu_serial is None:

        imu_serial = serial.Serial(
            port=PORT,
            baudrate=BAUDRATE,
            bytesize=8,
            parity=serial.PARITY_NONE,
            stopbits=1,
            timeout=0.5
        )


def read():

    try:

        connect()

        command = make_read_command(
            SLAVE_ID,
            0x003A,
            13
        )

        imu_serial.reset_input_buffer()

        imu_serial.write(command)
        imu_serial.flush()

        response = imu_serial.read(31)

        if len(response) != 31:
            return None

        if response[0] != SLAVE_ID:
            return None

        if response[1] != 0x03:
            return None

        if response[2] != 26:
            return None

        received_crc = (
            response[-2]
            | (response[-1] << 8)
        )

        calculated_crc = modbus_crc(
            response[:-2]
        )

        if received_crc != calculated_crc:
            return None

        data = response[3:-2]

        # 가속도
        ax_raw = int16(data[0], data[1])
        ay_raw = int16(data[2], data[3])
        az_raw = int16(data[4], data[5])

        # 자이로
        gx_raw = int16(data[6], data[7])
        gy_raw = int16(data[8], data[9])
        gz_raw = int16(data[10], data[11])

        # 각도
        roll_raw = int16(data[12], data[13])
        pitch_raw = int16(data[14], data[15])
        yaw_raw = int16(data[16], data[17])

        # 가속도 ±16g
        ax_g = ax_raw / 32768.0 * 16
        ay_g = ay_raw / 32768.0 * 16
        az_g = az_raw / 32768.0 * 16

        ax_ms2 = ax_g * G
        ay_ms2 = ay_g * G
        az_ms2 = az_g * G

        # 각속도 ±2000 °/s
        gx = gx_raw / 32768.0 * 2000
        gy = gy_raw / 32768.0 * 2000
        gz = gz_raw / 32768.0 * 2000

        # 각도 ±180°
        roll = roll_raw / 32768.0 * 180
        pitch = pitch_raw / 32768.0 * 180
        yaw = yaw_raw / 32768.0 * 180

        return {

            "acc": {
                "x": ax_ms2,
                "y": ay_ms2,
                "z": az_ms2
            },

            "gyro": {
                "x": gx,
                "y": gy,
                "z": gz
            },

            "angle": {
                "roll": roll,
                "pitch": pitch,
                "yaw": yaw
            }
        }

    except Exception as e:

        print(f"[IMU ERROR] {e}")
        return None


def close():

    global imu_serial

    if imu_serial is not None:

        if imu_serial.is_open:
            imu_serial.close()

        imu_serial = None


if __name__ == "__main__":

    print("WT901C485 Test")
    print("------------------------------")

    try:

        while True:

            data = read()

            if data is not None:

                print(
                    f"ACC "
                    f"X:{data['acc']['x']:.3f} "
                    f"Y:{data['acc']['y']:.3f} "
                    f"Z:{data['acc']['z']:.3f} m/s²"
                )

                print(
                    f"GYRO "
                    f"X:{data['gyro']['x']:.2f} "
                    f"Y:{data['gyro']['y']:.2f} "
                    f"Z:{data['gyro']['z']:.2f} °/s"
                )

                print(
                    f"ANGLE "
                    f"Roll:{data['angle']['roll']:.2f}° "
                    f"Pitch:{data['angle']['pitch']:.2f}° "
                    f"Yaw:{data['angle']['yaw']:.2f}°"
                )

                print("------------------------------")

            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\n종료")

    finally:
        close()