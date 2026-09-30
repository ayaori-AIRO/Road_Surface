import socket
import json


class TCPClient:

    def __init__(self, host, port):

        self.host = host
        self.port = port

        self.sock = None


    def connect(self):

        if self.sock is not None:
            return True

        try:

            self.sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )

            self.sock.settimeout(3)

            self.sock.connect(
                (self.host, self.port)
            )

            print(
                f"[TCP] Jetson 연결 성공 "
                f"{self.host}:{self.port}"
            )

            return True

        except Exception as e:

            print(f"[TCP] 연결 실패: {e}")

            if self.sock is not None:
                self.sock.close()

            self.sock = None

            return False


    def send(self, data):

        if self.sock is None:

            if not self.connect():
                return False

        try:

            # Python dict → JSON
            message = json.dumps(
                data,
                ensure_ascii=False
            )

            # JSON 한 메시지의 끝을 \n으로 표시
            message += "\n"

            self.sock.sendall(
                message.encode("utf-8")
            )

            return True

        except Exception as e:

            print(f"[TCP] 전송 실패: {e}")

            self.close()

            return False


    def close(self):

        if self.sock is not None:

            try:
                self.sock.close()
            except:
                pass

            self.sock = None