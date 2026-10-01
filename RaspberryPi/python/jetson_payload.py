"""Jetson wire format: one UTF-8 JSON object followed by a newline."""
from datetime import datetime
import math


def build_payload(result, context, sample_time, now):
    def finite(value):
        return float(value) if isinstance(value, (int, float)) and math.isfinite(value) else None

    ages = {}
    def sensor(name):
        item = context.get(name)
        age = (now - item["received_monotonic"]) * 1000 if item else None
        ages[name] = age
        if age is None or not 0 <= age <= 3000 or item["value"] is None:
            return {}
        return item["value"]

    road, air = sensor("ct100"), sensor("ftm02")
    prediction_age = (now - sample_time) * 1000
    status = result["status"]
    if not 0 <= prediction_age <= 300:
        status = "prediction_stale"
    snow = finite(result.get("predicted_snow_height_m")) if status == "ok" else None
    return {
        "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "snow_height_mm": snow * 1000 if snow is not None else None,
        "road_temperature_c": finite(road.get("temperature")),
        "air_temperature_c": finite(air.get("temperature")),
        "humidity_pct": finite(air.get("humidity")),
        "prediction_status": status,
        "sensor_age_ms": ages,
        "prediction_age_ms": prediction_age,
        "cycle_id": context.get("imu", {}).get("cycle_id"),
        "sensor_read_ms": {name: item["read_ms"] for name, item in context.items()},
    }
