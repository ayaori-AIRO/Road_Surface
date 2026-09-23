"""Send newline-delimited JSON to the Jetson receiver."""

import json
import socket


class TCPClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None

    def send(self, data):
        message = (json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
        try:
            if self.sock is None:
                self.sock = socket.create_connection((self.host, self.port), timeout=3)
                print(f"[TCP] Connected: {self.host}:{self.port}")
            self.sock.sendall(message)
            return True
        except OSError as error:
            print(f"[TCP] Send failed: {error}; retry on next sample")
            self.close()
            return False

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None
