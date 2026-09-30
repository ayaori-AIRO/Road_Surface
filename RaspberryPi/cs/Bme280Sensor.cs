// Compensation and measurement sequence adapted from Adafruit CircuitPython BME280 basic.py.
// Copyright (c) 2017 ladyada for Adafruit Industries. MIT; see THIRD_PARTY_NOTICES.md.
using System.Buffers.Binary;
using System.Device.I2c;
using System.Diagnostics;

namespace SensorBenchmark;

public sealed class Bme280Sensor : IDisposable
{
    private I2cDevice? device;
    private readonly double[] t = new double[3], p = new double[9], h = new double[6];

    private byte[] Read(byte register, int count)
    {
        byte[] result = new byte[count];
        device!.WriteRead(new byte[] { register }, result);
        return result;
    }
    private void Write(byte register, byte value) => device!.Write(new byte[] { register, value });
    private double Raw20(byte register)
    {
        byte[] b = Read(register, 3);
        return ((b[0] << 16) | (b[1] << 8) | b[2]) / 16.0;
    }

    private void Connect()
    {
        if (device is not null) return;
        int bus = int.Parse(Environment.GetEnvironmentVariable("BME_I2C_BUS") ?? "1");
        device = I2cDevice.Create(new I2cConnectionSettings(bus, 0x76));
        try
        {
            if (Read(0xD0, 1)[0] != 0x60) throw new IOException("BME280 chip ID 불일치");
            Write(0xE0, 0xB6);
            Thread.Sleep(4);
            byte[] calibration = Read(0x88, 24);
            for (int i = 0; i < 12; i++)
            {
                double value = i is 0 or 3
                    ? BinaryPrimitives.ReadUInt16LittleEndian(calibration.AsSpan(i * 2, 2))
                    : BinaryPrimitives.ReadInt16LittleEndian(calibration.AsSpan(i * 2, 2));
                if (i < 3) t[i] = value;
                else p[i - 3] = value;
            }
            h[0] = Read(0xA1, 1)[0];
            byte[] humidity = Read(0xE1, 7);
            h[1] = BinaryPrimitives.ReadInt16LittleEndian(humidity);
            h[2] = humidity[2];
            h[3] = ((sbyte)humidity[3] << 4) | (humidity[4] & 15);
            h[4] = ((sbyte)humidity[5] << 4) | (humidity[4] >> 4);
            h[5] = (sbyte)humidity[6];
            Write(0xF2, 1); // Humidity x1
            Write(0xF4, 0x34); // Temperature x1, pressure x16, sleep
            Write(0xF5, 0); // Filter off
        }
        catch { device.Dispose(); device = null; throw; }
    }

    private int MeasureTemperatureFine()
    {
        Write(0xF2, 1);
        Write(0xF4, 0x35); // Forced measurement, same defaults as Adafruit basic.
        var timer = Stopwatch.StartNew();
        while ((Read(0xF3, 1)[0] & 8) != 0)
        {
            if (timer.ElapsedMilliseconds > 1000) throw new TimeoutException("BME280 측정 완료 대기 초과");
            Thread.Sleep(2);
        }
        double raw = Raw20(0xFA);
        double a = (raw / 16384.0 - t[0] / 1024.0) * t[1];
        double b = raw / 131072.0 - t[0] / 8192.0;
        return (int)(a + b * b * t[2]);
    }

    public BmeData ReadData()
    {
        Connect();
        // Python accesses three properties: each triggers its own conversion.
        double temperature = MeasureTemperatureFine() / 5120.0;
        int fine = MeasureTemperatureFine();
        byte[] rawH = Read(0xFD, 2);
        double humidity = CompensateHumidity((rawH[0] << 8) | rawH[1], fine, h);
        fine = MeasureTemperatureFine();
        double pressure = CompensatePressure(Raw20(0xF7), fine, p);
        return new(temperature, humidity, pressure);
    }

    public static double CompensateHumidity(double raw, int fine, double[] calibration)
    {
        double delta = fine - 76800.0;
        double adjusted = raw - (calibration[3] * 64 + calibration[4] / 16384 * delta);
        double factor = 1 + calibration[2] / 67108864 * delta;
        double value = adjusted * (calibration[1] / 65536) *
            (factor * (1 + calibration[5] / 67108864 * delta * factor));
        return Math.Clamp(value * (1 - calibration[0] * value / 524288), 0, 100);
    }

    public static double CompensatePressure(double raw, int fine, double[] c)
    {
        double a = fine / 2.0 - 64000;
        double b = a * a * c[5] / 32768 + a * c[4] * 2;
        b = b / 4 + c[3] * 65536;
        double d = c[2] * a * a / 524288;
        a = (1 + (d + c[1] * a) / 524288 / 32768) * c[0];
        if (a == 0) throw new InvalidDataException("BME280 압력 보정 계수 오류");
        double pressure = ((1048576 - raw - b / 4096) * 6250) / a;
        return (pressure + (c[8] * pressure * pressure / 2147483648 +
            pressure * c[7] / 32768 + c[6]) / 16) / 100;
    }

    public void Dispose() => device?.Dispose();
}
