from simulator import run, wave


def read():
    temperature = wave(25.3, 1)
    humidity = wave(54, 5, 45)
    # Same configured 0-10 V scale as the current sensor application.
    return {
        "temperature": temperature,
        "humidity": humidity,
        "temperature_voltage": (temperature + 20) / 10,
        "humidity_voltage": humidity / 10,
    }


if __name__ == "__main__":
    run([("ftm02", read)])
