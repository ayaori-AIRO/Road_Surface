from simulator import run, wave


def read():
    temperature = wave(32, 3)
    return {"temperature": temperature, "current": 4 + (temperature + 20) / 120 * 16}


if __name__ == "__main__":
    run([("ct100", read)])
