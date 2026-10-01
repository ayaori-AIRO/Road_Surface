"""TCP telemetry + dependency-free dashboard. Run: python3 Jetson/tcp_server.py"""
import argparse
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import socketserver
import threading
import time

FIELDS = ('snow_height_mm', 'road_temperature_c', 'air_temperature_c', 'humidity_pct')


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.rows = deque(maxlen=36000)  # One hour at 10 Hz; memory only.
        self.sequence = 0
        self.clients = 0
        self.invalid = 0

    def add(self, packet):
        if not isinstance(packet, dict) or not all(k in packet for k in FIELDS):
            raise ValueError('Expected the four telemetry fields')
        row = {k: packet[k] for k in FIELDS}
        for value in row.values():
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError('Measurements must be finite numbers or null')
        row.update(timestamp=str(packet.get('timestamp', ''))[:80],
                   prediction_status=str(packet.get('prediction_status', 'unknown'))[:80],
                   received_ms=round(time.time()*1000))
        with self.lock:
            self.sequence += 1
            row['id'] = self.sequence
            self.rows.append(row)

    def snapshot(self, after):
        with self.lock:
            return {'rows': [r for r in self.rows if r['id'] > after],
                    'connected': self.clients > 0, 'invalid': self.invalid,
                    'latest': self.rows[-1] if self.rows else None, 'server_ms': round(time.time()*1000)}


class TCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class Receiver(socketserver.StreamRequestHandler):
    def handle(self):
        store = self.server.store
        with store.lock:
            store.clients += 1
        print('Connected:', self.client_address)
        try:
            while True:
                raw = self.rfile.readline(65537)
                if not raw:
                    break
                if len(raw) > 65536:
                    break
                if not raw.strip():
                    continue
                try:
                    store.add(json.loads(raw))
                except (ValueError, UnicodeError):
                    with store.lock:
                        store.invalid += 1
        except (ConnectionError, OSError):
            pass
        finally:
            with store.lock:
                store.clients -= 1
            print('Disconnected:', self.client_address)


class Web(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        url = urlparse(self.path)
        if url.path == '/api/data':
            try:
                after = max(0, int(parse_qs(url.query).get('after', ['0'])[0]))
            except ValueError:
                self.send_error(400)
                return
            data = json.dumps(self.server.store.snapshot(after), allow_nan=False).encode()
            kind = 'application/json'
        elif url.path == '/':
            data = Path(__file__).with_name('dashboard.html').read_bytes()
            kind = 'text/html; charset=utf-8'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', kind)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=5000)
    parser.add_argument('--web-port', type=int, default=8080)
    args = parser.parse_args()
    store = Store()
    with TCPServer((args.host, args.port), Receiver) as tcp, ThreadingHTTPServer((args.host, args.web_port), Web) as web:
        tcp.store = web.store = store
        thread = threading.Thread(target=tcp.serve_forever, daemon=True)
        thread.start()
        print(f'TCP :{args.port} | Dashboard http://localhost:{args.web_port}')
        try:
            web.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            tcp.shutdown()


if __name__ == '__main__':
    main()
