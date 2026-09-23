from simulator import run, wave


def read():
    return {
        "acc": {"x": wave(0, 0.2, 7), "y": wave(0, 0.15, 9), "z": wave(9.80665, 0.1, 5)},
        "gyro": {"x": wave(0, 1, 7), "y": wave(0, 0.8, 9), "z": wave(0, 0.5, 11)},
        "angle": {"roll": wave(0, 2, 20), "pitch": wave(0, 1.5, 25), "yaw": wave(90, 3, 40)},
    }


if __name__ == "__main__":
    run([("imu", read)])
