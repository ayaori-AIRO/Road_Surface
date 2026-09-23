from simulator import run, wave


def read():
    return {"temperature": wave(25, 1), "humidity": wave(55, 5, 45), "pressure": wave(1013.25, 1.5, 60)}


if __name__ == "__main__":
    run([("bme280", read)])
