import bme280
import ct100
import ftm02
import gps
import imu
from simulator import run
from noise_predict import NoisePredictor


if __name__ == "__main__":
    run([
        ("ct100", ct100.read),
        ("ftm02", ftm02.read),
        ("bme280", bme280.read),
        ("gps", gps.read),
        ("imu", imu.read),
    ], tcp=True, predictor=NoisePredictor())
