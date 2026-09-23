import socket
import json


HOST = "0.0.0.0"
PORT = 5000


server = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)

server.setsockopt(
    socket.SOL_SOCKET,
    socket.SO_REUSEADDR,
    1
)

server.bind(
    (HOST, PORT)
)

server.listen(1)


print("========================================")
print("Road Surface TCP Server")
print(f"PORT : {PORT}")
print("Raspberry Pi 연결 대기 중...")
print("========================================")


while True:

    client, address = server.accept()

    print()
    print(
        f"Raspberry Pi 연결됨 : "
        f"{address[0]}:{address[1]}"
    )

    buffer = ""

    try:

        while True:

            data = client.recv(4096)

            if not data:
                break

            buffer += data.decode(
                "utf-8",
                errors="ignore"
            )

            # \n 기준으로 JSON 메시지 분리
            while "\n" in buffer:

                line, buffer = buffer.split(
                    "\n",
                    1
                )

                if not line.strip():
                    continue

                try:

                    sensor_data = json.loads(line)

                    print()
                    print("========================================")
                    print(
                        "TIME:",
                        sensor_data.get("timestamp")
                    )

                    print(
                        "CT100:",
                        sensor_data.get("ct100")
                    )

                    print(
                        "FTM02:",
                        sensor_data.get("ftm02")
                    )

                    print(
                        "BME280:",
                        sensor_data.get("bme280")
                    )

                    print(
                        "GPS:",
                        sensor_data.get("gps")
                    )

                    print(
                        "IMU:",
                        sensor_data.get("imu")
                    )

                    if sensor_data.get("simulation"):
                        print("[SIMULATION] Generated sensor values")
                    if "predicted_noise_m" in sensor_data:
                        print("Predicted Noise (m):", sensor_data["predicted_noise_m"])
                        print("Temperature/Humidity source:", sensor_data.get("noise_environment_sensor"))

                except json.JSONDecodeError as e:

                    print(
                        "[JSON ERROR]",
                        e
                    )

    except Exception as e:

        print(
            "[TCP ERROR]",
            e
        )

    finally:

        client.close()

        print()
        print("Raspberry Pi 연결 종료")
        print("다시 연결 대기...")
