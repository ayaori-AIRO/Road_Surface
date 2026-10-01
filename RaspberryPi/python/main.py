"""Run from repo root: python3 -m RaspberryPi.python.main

Offline smoke test: python -m RaspberryPi.python.main --simulate --no-tcp --duration 3
Default: real FTM02/IMU, synthetic distance/speed, gyro inputs fixed to zero.
"""
import argparse
from datetime import datetime
import math
from pathlib import Path
from queue import Queue, Empty
import threading
import time

if __package__:
    from .live_prediction import Predictor, Latest, poll_sensor, input_values, replace_latest
    from .tcp_client import TCPClient
else:
    from live_prediction import Predictor, Latest, poll_sensor, input_values, replace_latest
    from tcp_client import TCPClient

JETSON_IP = "192.168.1.163"
JETSON_PORT = 5000
MODEL_PATH = Path(__file__).resolve().parents[2] / "ML/python/models/total_noise_model_accel_history_complete.joblib"


def simulated_readers():
    start = time.monotonic()
    def imu_read():
        t = time.monotonic()-start
        return {"acc": {"x": (1.039+.025*math.sin(2*math.pi*.65*t))*9.80665,
                        "y": .05*9.80665, "z": .038*9.80665},
                "gyro": dict(x=0., y=0., z=0.),
                "angle": dict(roll=0., pitch=0., yaw=0.)}
    return {"imu": (imu_read, .1),
            "ftm02": (lambda: dict(temperature=15.5, humidity=23.), 1.),
            "gps": (lambda: dict(fix=True, speed_kmh=30.), .5)}


def transmit(tcp, queue, stop):
    try:
        while not stop.is_set():
            try:
                payload = queue.get(timeout=.2)
            except Empty:
                continue
            tcp.send(payload)
    finally:
        tcp.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    parser.add_argument("--speed-source", choices=["synthetic", "gps"], default="synthetic")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--no-tcp", action="store_true")
    parser.add_argument("--duration", type=float, default=0, help="0 runs until Ctrl+C")
    parser.add_argument("--aux-sensors", action="store_true", help="also poll CT100 and BME280")
    args = parser.parse_args()
    predictor = Predictor(args.model)
    cleanup = []
    if args.simulate:
        readers = simulated_readers()
    else:
        if __package__:
            from . import ftm02, imu, gps
        else:
            import ftm02, imu, gps
        readers = {"imu": (imu.read, .1), "ftm02": (ftm02.read, 1.), "gps": (gps.read_speed, .1)}
        cleanup = [imu.close, gps.close]
        if args.aux_sensors:
            if __package__:
                from . import ct100, bme280
            else:
                import ct100, bme280
            readers.update(ct100=(ct100.read, 1.), bme280=(bme280.read, 1.))
    latest, stop = Latest(), threading.Event()
    samples, outgoing = Queue(maxsize=2), Queue(maxsize=1)
    threads = []
    start = time.monotonic()
    print("10 Hz IMU / 1s history model / reference 3.1715 m")
    print(f"Speed: {args.speed_source}; distance: SYNTHETIC; model gyro: ZERO")
    print("Sensor ages are time since receipt, not hardware measurement age.")
    if args.simulate:
        print("SIMULATED SENSORS: pipeline test only")
    counts = dict(samples=0, predicted=0, waiting=0)
    last_print = -math.inf
    try:
        for name, (reader, period) in readers.items():
            thread = threading.Thread(target=poll_sensor,
                args=(name, reader, period, latest, stop, samples if name == "imu" else None),
                name=name, daemon=True)
            thread.start()
            threads.append(thread)
        if not args.no_tcp:
            thread = threading.Thread(target=transmit,
                args=(TCPClient(JETSON_IP,JETSON_PORT), outgoing, stop), daemon=True)
            thread.start()
            threads.append(thread)
        while not args.duration or time.monotonic()-start < args.duration:
            try:
                event = samples.get(timeout=.2)
            except Empty:
                continue
            counts["samples"] += 1
            stamp = event["sample_time"]
            base, ages, status = input_values(event, args.speed_source, stamp-start)
            if event["value"] is None:
                predictor.reset()
                result = {"status": "imu_missing"}
            elif time.monotonic()-stamp > .2:
                predictor.reset()
                result = {"status": "imu_processing_late"}
            else:
                acc = event["value"]["acc"]
                predictor.add(stamp, [acc[a]/9.80665 for a in "xyz"])
                if base is not None:
                    base.update({f"accel_{a}_g": acc[a]/9.80665 for a in "xyz"})
                result = predictor.predict(base) if base is not None else {"status": status}
            counts["predicted" if result["status"] == "ok" else "waiting"] += 1
            elapsed = time.monotonic()-stamp
            payload = {"timestamp": datetime.now().isoformat(timespec="milliseconds"),
                       "sample_elapsed_s": stamp-start,
                       "imu": event["value"], "ftm02": event["context"].get("ftm02",{}).get("value"),
                       "gps": event["context"].get("gps",{}).get("value"),
                       "model_input": base, "prediction": result,
                       "sources": {"distance": "synthetic", "speed": args.speed_source,
                                   "gyro": "fixed_zero", "imu": "simulated" if args.simulate else "sensor"},
                       "timing": {"imu_read_ms": event["read_ms"], "imu_interval_ms": event["interval_ms"],
                                  "sensor_age_ms": ages, "sample_to_result_ms": elapsed*1000}}
            if not args.no_tcp:
                replace_latest(outgoing, payload)
            if time.monotonic()-last_print >= 1.:
                print(f"\n{payload['timestamp']} | IMU interval={event['interval_ms']} ms | read={event['read_ms']:.3f} ms")
                print("Sensor age (ms):", ages)
                for name, item in latest.snapshot().items():
                    print(f"{name.upper()}: read={item['read_ms']:.3f} ms | {item['value']}")
                print("Model inputs:", base)
                print("Prediction:", result)
                print(f"Sample to result: {elapsed*1000:.3f} ms")
                last_print = time.monotonic()
    except KeyboardInterrupt:
        print("Stopped")
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=5.)
        # Do not close a port while its reader is still running.
        if not any(t.is_alive() for t in threads if t.name in ("imu","gps")):
            for close in cleanup:
                close()
        predictor.close()
        print("Totals:", counts)


if __name__ == "__main__":
    main()
