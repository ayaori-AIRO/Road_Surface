"""Predict distance noise from one snapshot of simulated sensor readings."""

from pathlib import Path

import joblib
import pandas as pd


MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "noise_predict_model.joblib"
GRAVITY = 9.80665


class NoisePredictor:
    def __init__(self, model_path=MODEL_PATH, environment_sensor="ftm02"):
        if environment_sensor not in ("ftm02", "bme280"):
            raise ValueError("Temperature/humidity source must be ftm02 or bme280")
        artifact = joblib.load(model_path)
        self.model = artifact["model"]
        self.feature_columns = artifact["feature_columns"]
        self.environment_sensor = environment_sensor

    def build_features(self, readings):
        motion = readings["imu"]
        environment = readings[self.environment_sensor]
        # IMU displays m/s²; the trained model expects g. Gyro already uses deg/s.
        values = {
            "Speed(km/h)": readings["gps"]["speed_kmh"],
            "AccelX(g)": motion["acc"]["x"] / GRAVITY,
            "AccelY(g)": motion["acc"]["y"] / GRAVITY,
            "AccelZ(g)": motion["acc"]["z"] / GRAVITY,
            "GyroX(deg/s)": motion["gyro"]["x"],
            "GyroY(deg/s)": motion["gyro"]["y"],
            "GyroZ(deg/s)": motion["gyro"]["z"],
            "Temperature(°C)": environment["temperature"],
            "Humidity(%)": environment["humidity"],
        }
        return pd.DataFrame([[values[column] for column in self.feature_columns]], columns=self.feature_columns)

    def predict(self, readings):
        return float(self.model.predict(self.build_features(readings))[0])
