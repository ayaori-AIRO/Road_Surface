"""Live 10 Hz acquisition and inference. All times below use a monotonic clock."""
from collections import deque
import math
import threading
import time

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

G = 9.80665


class Latest:
    def __init__(self):
        self.lock = threading.Lock()
        self.values = {}

    def put(self, name, value, stamp, read_ms):
        with self.lock:
            self.values[name] = {"value": value, "received_monotonic": stamp,
                                 "read_ms": read_ms}

    def snapshot(self):
        with self.lock:
            return self.values.copy()


def poll_sensor(name, reader, period, latest, stop, samples=None):
    """Schedule start-to-start, skip missed deadlines instead of bursting reads."""
    deadline = time.monotonic()
    previous = None
    while not stop.is_set():
        if stop.wait(max(0, deadline-time.monotonic())):
            return
        start = time.monotonic()
        context = latest.snapshot() if samples is not None else None
        try:
            value = reader()
        except Exception as e:
            value = None
            print(f"[{name.upper()} ERROR] {e}")
        end = time.monotonic()
        read_ms = (end-start)*1000
        latest.put(name, value, end, read_ms)
        if samples is not None:
            event = {"value": value, "sample_time": start, "read_ms": read_ms,
                     "interval_ms": (start-previous)*1000 if previous is not None else None,
                     "context": context}
            replace_latest(samples, event)
        previous = start
        deadline += period
        if deadline < end:
            deadline += (math.floor((end-deadline)/period)+1)*period


def replace_latest(queue, value):
    """A bounded queue never blocks acquisition; gaps trigger history reset."""
    from queue import Empty, Full
    try:
        queue.put_nowait(value)
    except Full:
        try:
            queue.get_nowait()
        except Empty:
            pass
        try:
            queue.put_nowait(value)
        except Full:
            pass


class Predictor:
    def __init__(self, path, reference=3.1715, gap_tolerance=.025):
        self.artifact = joblib.load(path)
        self.n = int(self.artifact["history_seconds"]*10)
        self.history = deque(maxlen=self.n+1)
        self.reference = reference
        self.gap_tolerance = gap_tolerance
        # Initialize native inference once before acquisition starts.
        self.thread_limits = threadpool_limits(limits=1)
        warmup = pd.DataFrame(np.zeros((1, len(self.artifact["feature_columns"]))),
                              columns=self.artifact["feature_columns"])
        self.artifact["model"].predict(warmup)

    def close(self):
        self.thread_limits.restore_original_limits()

    def reset(self):
        self.history.clear()

    def add(self, stamp, acceleration):
        if self.history:
            dt = stamp-self.history[-1][0]
            if abs(dt-.1) > self.gap_tolerance:
                self.reset()
        if not np.isfinite(acceleration).all():
            self.reset()
            return
        self.history.append((stamp, np.asarray(acceleration, dtype=float)))

    def features(self, base):
        if len(self.history) < self.n+1:
            return None
        values = np.stack([item[1] for item in self.history])
        row = dict(base)
        for j, axis in enumerate(("accel_x_g", "accel_y_g", "accel_z_g")):
            # Match offline make_features: rolling N includes current + N-1 past.
            v = values[-self.n:, j]
            row[axis] = float(values[-1,j])
            row[axis+"_mean"] = float(v.mean())
            row[axis+"_std"] = float(v.std(ddof=0))
            row[axis+"_range"] = float(np.ptp(v))
            row[axis+"_rms"] = float(np.sqrt(np.mean(v*v)))
            row[axis+"_delta"] = float(values[-1,j]-values[-2,j])
            for lag in (1,2,5,10,20,30,40,50):
                if lag <= self.n:
                    row[f"{axis}_lag_{lag}"] = float(values[-1-lag,j])
        row["history_samples_available"] = self.n
        return pd.DataFrame([row], columns=self.artifact["feature_columns"])

    def predict(self, base):
        start = time.perf_counter()
        x = self.features(base)
        if x is None:
            return {"status": "warming_up", "samples": len(self.history),
                    "required_samples": self.n+1}
        feature_ms = (time.perf_counter()-start)*1000
        inference_start = time.perf_counter()
        noise = float(self.artifact["model"].predict(x)[0])
        if not math.isfinite(noise):
            raise ValueError("Non-finite prediction")
        corrected = base["distance_measured_m"]-noise
        return {"status": "ok", "predicted_total_noise_m": noise,
                "corrected_distance_m": corrected,
                "predicted_snow_height_m": self.reference-corrected,
                "feature_ms": feature_ms,
                "inference_ms": (time.perf_counter()-inference_start)*1000,
                "total_prediction_ms": (time.perf_counter()-start)*1000}


def input_values(event, speed_source, elapsed, max_ftm_age=3., max_speed_age=2.):
    """Only values already received before IMU acquisition started are eligible."""
    stamp = event["sample_time"]
    context = event["context"]
    ftm = context.get("ftm02")
    ages = {}
    if not ftm or ftm["value"] is None:
        return None, ages, "waiting_for_ftm02"
    ages["ftm02_ms"] = (stamp-ftm["received_monotonic"])*1000
    if not 0 <= ages["ftm02_ms"] <= max_ftm_age*1000:
        return None, ages, "ftm02_stale"
    if speed_source == "gps":
        gps = context.get("gps")
        if not gps or gps["value"] is None:
            return None, ages, "waiting_for_gps_speed"
        ages["gps_ms"] = (stamp-gps["received_monotonic"])*1000
        if not 0 <= ages["gps_ms"] <= max_speed_age*1000:
            return None, ages, "gps_speed_stale"
        speed = gps["value"]["speed_kmh"]
    else:
        speed = 30+5*math.sin(.2*elapsed)
    base = {"distance_measured_m": 3.1715-.08+.005*math.sin(2*math.pi*.65*elapsed),
            "speed_kmh": speed, "gyro_x_dps": 0., "gyro_y_dps": 0., "gyro_z_dps": 0.,
            "temperature_c": ftm["value"]["temperature"],
            "humidity_pct": ftm["value"]["humidity"]}
    if not all(math.isfinite(float(v)) for v in base.values()):
        return None, ages, "invalid_input"
    return base, ages, "ready"
