"""Run from repo root: python3 -m RaspberryPi.python.main

Offline smoke test: python -m RaspberryPi.python.main --simulate --no-tcp --duration 3
Default: real CT100/FTM02/IMU/BME280, synthetic distance/speed, gyro inputs fixed to zero.
"""
import argparse
from datetime import datetime
import math
from pathlib import Path
from queue import Queue, Empty
import threading
import time

if __package__:
    from .live_prediction import Predictor, input_values, replace_latest
    from .tcp_client import TCPClient
    from .jetson_payload import build_payload
    from .cycle_acquisition import acquire_cycles
else:
    from live_prediction import Predictor, input_values, replace_latest
    from tcp_client import TCPClient
    from jetson_payload import build_payload
    from cycle_acquisition import acquire_cycles

JETSON_IP = "192.168.1.163"
JETSON_PORT = 5000
MODEL_PATH = Path(__file__).resolve().parents[2] / "ML/python/models/total_noise_model_accel_history_complete_pi.joblib"
CYCLE_SECONDS = 1.0


class ContinuousImu:
    """One serial reader; the prediction thread consumes timestamped history."""
    def __init__(self, read, stop):
        from collections import deque
        self.reader, self.stop = read, stop
        self.lock = threading.Lock()
        self.samples = deque(maxlen=1000)
        self.selected = []

    def run(self):
        deadline = time.monotonic()
        while not self.stop.wait(max(0., deadline-time.monotonic())):
            stamp = time.monotonic()
            try:
                value = self.reader()
            except Exception as error:
                print(f"[IMU ERROR] {error}")
                value = None
            with self.lock:
                self.samples.append((stamp, time.monotonic(), value))
            deadline += .1
            now = time.monotonic()
            if deadline < now:
                deadline += (math.floor((now-deadline)/.1)+1)*.1

    def read(self):
        # Select a genuinely new sample from this acquisition cycle.
        start = time.monotonic()
        self.selected = []
        while not self.stop.is_set():
            with self.lock:
                if self.samples and self.samples[-1][0] >= start:
                    self.selected = list(self.samples)
                    return self.selected[-1][2]
            if time.monotonic()-start >= .3:
                return None
            self.stop.wait(.002)
        return None


def simulated_readers():
    start = time.monotonic()
    def imu_read():
        t = time.monotonic()-start
        return {"acc": {"x": (1.039+.025*math.sin(2*math.pi*.65*t))*9.80665,
                        "y": .05*9.80665, "z": .038*9.80665},
                "gyro": dict(x=0., y=0., z=0.),
                "angle": dict(roll=0., pitch=0., yaw=0.)}
    return {"imu": (imu_read, .1),
            "ct100": (lambda: dict(temperature=12.5), 1.),
            "ftm02": (lambda: dict(temperature=15.5, humidity=23.), 1.),
            "bme280": (lambda: dict(temperature=15.5, humidity=23., pressure=1013.25), 1.),
            "gps": (lambda: dict(fix=True, speed_kmh=30.), .5)}


def transmit(tcp, queue, stop):
    """Send each completed batch at its own cycle-start + 1000 ms deadline."""
    try:
        while not stop.is_set():
            try:
                result, context, stamp, deadline = queue.get(timeout=.2)
            except Empty:
                continue
            if not tcp.connect():
                continue
            if stop.wait(max(0., deadline-time.monotonic())):
                break
            # Do not replay a missed cycle after a long network outage.
            if time.monotonic() >= deadline + CYCLE_SECONDS:
                continue
            tcp.send(build_payload(result, context, stamp, time.monotonic()))
    finally:
        tcp.close()


def format_status(payload, sensors):
    """Round console values only; retain full precision in the TCP payload."""
    def number(value, digits=1):
        return "--" if value is None else f"{value:.{digits}f}"

    def axes(values, names, digits):
        return "  ".join(f"{axis.upper()}={number(values.get(axis), digits):>8}" for axis in names)

    result, timing = payload["prediction"], payload["timing"]
    labels = {"ok": "정상", "warming_up": "이력 수집 중",
              "cycle_late": "수집·예측 지연 (1000ms 초과)", "cycle_mismatch": "센서 회차 불일치",
              "ftm02_missing": "온습도 수신 실패", "ct100_missing": "노면 온도 수신 실패",
              "gps_missing": "GPS 수신 실패",
              "imu_missing": "IMU 수신 없음", "imu_processing_late": "IMU 처리 지연",
              "waiting_for_ftm02": "온습도 수신 대기", "ftm02_stale": "온습도 갱신 지연",
              "waiting_for_gps_speed": "GPS 속도 수신 대기", "gps_speed_stale": "GPS 갱신 지연",
              "invalid_input": "입력값 오류"}
    status = labels.get(result["status"], result["status"])
    if result["status"] == "warming_up":
        status += f" ({result['samples']}/{result['required_samples']})"
    lines = ["", "=" * 76, f"{payload['timestamp'].replace('T', ' ')}  |  예측: {status}"]
    if result["status"] == "ok":
        lines += [f"  적설 높이  {result['predicted_snow_height_m']*1000:9.2f} mm"
                  f"    예측 노이즈  {result['predicted_total_noise_m']*1000:+9.2f} mm",
                  f"  보정 거리  {result['corrected_distance_m']:9.4f} m"]
    lines += ["-" * 76, "[센서 | 같은 회차에서 새로 읽은 값]"]
    imu = payload["imu"]
    if imu:
        lines += ["  가속도 (m/s2) " + axes(imu.get("acc", {}), "xyz", 3),
                  "  각속도 (deg/s) " + axes(imu.get("gyro", {}), "xyz", 2),
                  "  자세   (deg)  " + axes(imu.get("angle", {}), ("roll", "pitch", "yaw"), 2)]
    else:
        lines.append("  IMU     수신 없음")
    ftm, gps = payload["ftm02"], payload["gps"]
    road = payload["ct100"]
    lines.append("  노면    " + (f"온도 {number(road.get('temperature'))} C" if road else "수신 없음"))
    lines.append("  온습도  " + (f"온도 {number(ftm.get('temperature'))} C  |  습도 {number(ftm.get('humidity'))} %" if ftm else "수신 없음"))
    lines.append("  GPS     " + (f"속도 {number(gps.get('speed_kmh'))} km/h  |  fix={gps.get('fix', '--')}" if gps else "수신 없음"))
    base, sources = payload["model_input"], payload["sources"]
    speed_source = "가상" if sources["speed"] == "synthetic" else "GPS"
    lines.append(f"[모델 입력 | 거리: 가상 / 속도: {speed_source} / 각속도: 0 고정]")
    if base:
        lines += [f"  거리 {base['distance_measured_m']:.4f} m  |  속도 {base['speed_kmh']:.1f} km/h",
                  "  가속도 (g)    " + axes({a: base.get(f"accel_{a}_g") for a in "xyz"}, "xyz", 4)]
    else:
        lines.append("  입력 준비 중")
    lines += ["[처리 시간]",
              f"  회차 {timing['cycle_id']}  |  전체 수집 {number(timing['acquisition_ms'])} ms",
              f"  회차 주기 {number(timing['imu_interval_ms'])} ms  |  IMU 새 샘플 대기 {number(timing['imu_read_ms'])} ms"
              f"  |  결과까지 {number(timing['sample_to_result_ms'])} ms"]
    if result["status"] == "ok":
        lines.append(f"  특징 계산 {number(result['feature_ms'])} ms  |  추론 {number(result['inference_ms'])} ms")
    ages = timing["sensor_age_ms"]
    if ages:
        lines.append("  예측 직전 수신 후 경과: " + "  |  ".join(f"{name.removesuffix('_ms').upper()} {value:.0f} ms" for name, value in ages.items()))
    for name, item in sorted(sensors.items()):
        if name != "imu":
            lines.append(f"  {name.upper():6} 이번 회차 읽기 {number(item['read_ms'])} ms")
        if name not in ("imu", "gps", "ftm02"):
            value = item["value"]
            detail = "  |  ".join(f"{k}={number(v, 3) if isinstance(v, (int, float)) else v}" for k, v in value.items()) if isinstance(value, dict) else str(value)
            lines.append(f"          {detail}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    parser.add_argument("--speed-source", choices=["synthetic", "gps"], default="synthetic")
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--no-tcp", action="store_true")
    parser.add_argument("--duration", type=float, default=0, help="0 runs until Ctrl+C")
    parser.add_argument("--aux-sensors", action="store_true", help="compatibility option; BME280 is collected by default")
    args = parser.parse_args()
    predictor = Predictor(args.model)
    cleanup = []
    if args.simulate:
        readers = simulated_readers()
    else:
        if __package__:
            from . import ct100, ftm02, imu, gps, bme280
        else:
            import ct100, ftm02, imu, gps, bme280
        readers = {"imu": (imu.read, .1), "ct100": (ct100.read, 1.),
                   "ftm02": (ftm02.read, 1.), "gps": (gps.read_speed, .1),
                   "bme280": (bme280.read, 1.)}
        cleanup = [imu.close, gps.close]
    # GPS participates only when its speed is actually used by the model.
    if args.speed_source != "gps":
        readers.pop("gps", None)
    stop = threading.Event()
    continuous_imu = ContinuousImu(readers["imu"][0], stop)
    readers["imu"] = (continuous_imu.read, CYCLE_SECONDS)
    last_imu_stamp = -math.inf
    outgoing = Queue(maxsize=1)
    threads = []
    start = time.monotonic()
    print("1 Hz acquisition/prediction/TCP / 10 Hz IMU history / reference 3.1715 m")
    print(f"Speed: {args.speed_source}; distance: SYNTHETIC; model gyro: ZERO")
    print("Same-cycle acquisition: fresh IMU/FTM02/CT100/BME280 before each prediction.")
    print("Acquisition target: 300 ms; ML before 1000 ms; send at cycle start + 1000 ms.")
    if args.simulate:
        print("SIMULATED SENSORS: pipeline test only")
    counts = dict(samples=0, predicted=0, waiting=0)
    try:
        imu_thread = threading.Thread(target=continuous_imu.run, name="imu", daemon=True)
        imu_thread.start()
        threads.append(imu_thread)
        print("Collecting initial IMU history for 1 second...")
        if stop.wait(1.):
            return
        if not args.no_tcp:
            thread = threading.Thread(target=transmit,
                args=(TCPClient(JETSON_IP,JETSON_PORT), outgoing, stop), daemon=True)
            thread.start()
            threads.append(thread)
        cycles = acquire_cycles(readers, stop, args.duration, period=CYCLE_SECONDS)
        for event in cycles:
            counts["samples"] += 1
            stamp = event["sample_time"]
            if continuous_imu.selected:
                imu_stamp, received, _ = continuous_imu.selected[-1]
                event["context"]["imu"].update(started_monotonic=imu_stamp,
                                                received_monotonic=received,
                                                read_ms=(received-imu_stamp)*1000)
            base, ages, status = input_values(event, args.speed_source, stamp-start)
            for imu_stamp, received, imu_value in continuous_imu.selected:
                if imu_stamp <= last_imu_stamp:
                    continue
                last_imu_stamp = imu_stamp
                if imu_value is None:
                    predictor.reset()
                else:
                    predictor.add(imu_stamp, [imu_value["acc"][a]/9.80665 for a in "xyz"])
            if event["value"] is None:
                predictor.reset()
                result = {"status": "imu_missing"}
            elif time.monotonic()-event["cycle_start"] > CYCLE_SECONDS:
                result = {"status": "cycle_late"}
            else:
                acc = event["value"]["acc"]
                if base is not None:
                    base.update({f"accel_{a}_g": acc[a]/9.80665 for a in "xyz"})
                result = predictor.predict(base) if base is not None else {"status": status}
            if time.monotonic()-event["cycle_start"] > CYCLE_SECONDS:
                result = {"status": "cycle_late"}
            counts["predicted" if result["status"] == "ok" else "waiting"] += 1
            elapsed = time.monotonic()-stamp
            payload = {"timestamp": datetime.now().isoformat(timespec="milliseconds"),
                       "sample_elapsed_s": stamp-start,
                       "imu": event["value"], "ftm02": event["context"].get("ftm02",{}).get("value"),
                       "gps": event["context"].get("gps",{}).get("value"),
                       "ct100": event["context"].get("ct100",{}).get("value"),
                       "model_input": base, "prediction": result,
                       "sources": {"distance": "synthetic", "speed": args.speed_source,
                                   "gyro": "fixed_zero", "imu": "simulated" if args.simulate else "sensor"},
                       "timing": {"imu_read_ms": event["read_ms"], "imu_interval_ms": event["interval_ms"],
                                  "acquisition_ms": event["acquisition_ms"], "cycle_id": event["cycle_id"],
                                  "sensor_age_ms": ages, "sample_to_result_ms": elapsed*1000}}
            if not args.no_tcp:
                replace_latest(outgoing, (result, event["context"], event["cycle_start"],
                                          event["cycle_start"] + CYCLE_SECONDS))
            if event["acquisition_ms"] > 300:
                print("[수집 지연] 300ms 목표 초과")
            print(format_status(payload, event["context"]))
    except KeyboardInterrupt:
        print("Stopped")
    finally:
        stop.set()
        if "cycles" in locals():
            cycles.close()
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
