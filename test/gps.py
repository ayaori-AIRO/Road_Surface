from simulator import run, wave


def read():
    return {
        "fix": True,
        "latitude": wave(37.5665, 0.0001, 60, 0.000001),
        "longitude": wave(126.978, 0.0001, 75, 0.000001),
        "altitude": wave(35, 0.5, 50),
        "satellites": round(wave(10, 2, 60, 0)),
        "quality": 1,
        "speed_kmh": wave(40, 10, 60, 0.1),
    }


if __name__ == "__main__":
    run([("gps", read)])
