"""Hardware-free sensor values and console display helpers."""

import argparse
from datetime import datetime
import math
import random
import time

_START = time.monotonic()


def wave(center, amplitude, period=30, noise=0.02):
    elapsed = time.monotonic() - _START
    return center + amplitude * math.sin(2 * math.pi * elapsed / period) + random.uniform(-noise, noise)


def display(name, data):
    print(f"[ {name.upper()} ]")
    if name == "bme280":
        print(f"Temperature : {data['temperature']:.2f} °C")
        print(f"Humidity    : {data['humidity']:.2f} %RH")
        print(f"Pressure    : {data['pressure']:.2f} hPa")
    elif name == "ct100":
        print(f"Temperature : {data['temperature']:.2f} °C")
        print(f"Current     : {data['current']:.3f} mA")
    elif name == "ftm02":
        print(f"Humidity Voltage    : {data['humidity_voltage']:.3f} V  Humidity: {data['humidity']:.2f} %RH")
        print(f"Temperature Voltage : {data['temperature_voltage']:.3f} V  Temperature: {data['temperature']:.2f} °C")
    elif name == "gps":
        print(f"Fix        : {data['fix']}")
        print(f"Latitude   : {data['latitude']:.6f}")
        print(f"Longitude  : {data['longitude']:.6f}")
        print(f"Altitude   : {data['altitude']:.1f} m")
        print(f"Satellites : {data['satellites']}")
        print(f"Quality    : {data['quality']}")
        print(f"Speed      : {data['speed_kmh']:.2f} km/h")
    elif name == "imu":
        for key, label, unit in (("acc", "ACC", "m/s²"), ("gyro", "GYRO", "°/s")):
            values = data[key]
            print(f"{label:5} : X={values['x']:.3f} Y={values['y']:.3f} Z={values['z']:.3f} {unit}")
        angles = data['angle']
        print(f"ANGLE : Roll={angles['roll']:.2f}° Pitch={angles['pitch']:.2f}° Yaw={angles['yaw']:.2f}°")
    print()


def run(sensors, tcp=False, predictor=None):
    parser = argparse.ArgumentParser(description="Simulated sensor output with optional Jetson TCP transmission.")
    parser.add_argument("--interval", type=float, default=1.0, help="Seconds between readings")
    parser.add_argument("--count", type=int, default=0, help="Number of readings; 0 runs until Ctrl+C")
    if tcp:
        parser.add_argument("--host", default="10.42.0.1", help="Jetson IP address")
        parser.add_argument("--port", type=int, default=5000, help="Jetson TCP port")
        parser.add_argument("--no-tcp", action="store_true", help="Display locally without TCP")
    args = parser.parse_args()
    if not math.isfinite(args.interval) or args.interval <= 0 or args.count < 0:
        parser.error("interval must be positive and finite; count must be nonnegative")
    client = None
    if tcp and not args.no_tcp:
        if not 1 <= args.port <= 65535:
            parser.error("port must be between 1 and 65535")
        from tcp_client import TCPClient
        client = TCPClient(args.host, args.port)
    print("[SIMULATION] Generated sensor values | Ctrl+C to stop", flush=True)
    index = 0
    try:
        while args.count == 0 or index < args.count:
            index += 1
            now = datetime.now()
            print("=" * 54)
            print(f"TIME : {now:%Y-%m-%d %H:%M:%S}  Sample: {index}")
            print("=" * 54)
            readings = {}
            for name, read in sensors:
                readings[name] = read()
                display(name, readings[name])
            payload = {"timestamp": now.isoformat(timespec="milliseconds"),
                       "simulation": True, "sample": index, **readings}
            if predictor is not None:
                noise = predictor.predict(readings)
                payload["predicted_noise_m"] = noise
                payload["noise_environment_sensor"] = predictor.environment_sensor
                print("[ NOISE PREDICTION | simulated inputs ]")
                print(f"Predicted Noise : {noise:+.6f} m ({noise * 100:+.3f} cm)")
                print(f"Temperature / Humidity source: {predictor.environment_sensor.upper()}")
                print()
            if client is not None:
                if client.send(payload):
                    print("[TCP] Sent sensor values and prediction to Jetson")
            print(flush=True)
            if args.count == 0 or index < args.count:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nSimulation stopped.")
    finally:
        if client is not None:
            client.close()
