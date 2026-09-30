using System.Buffers.Binary;
using System.Text;

namespace SensorBenchmark;

internal static class SelfTest
{
    public static int Run()
    {
        try
        {
            Check(SerialSensors.Crc(Encoding.ASCII.GetBytes("123456789")) == 0x4B37, "Modbus CRC known vector");
            var gps = SerialSensors.ParseGga("$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*47");
            Check(gps is { Fix: true, Satellites: 8 } && Math.Abs(gps.Latitude!.Value - 48.1173) < 1e-7, "GGA coordinate");
            Check(SerialSensors.ParseGga("$GPGGA,123519,4807.038,N,01131.000,E,1,08,0.9,545.4,M,46.9,M,,*00") is null, "GGA bad checksum");
            Check(SerialSensors.ParseGga("$GNGGA,123519,,,,,0,00,99.9,,M,,M,,") is { Fix: false }, "GGA no fix");
            Check(AnalogSensors.CurrentToTemperature(4) == -20 && AnalogSensors.CurrentToTemperature(20) == 100, "4-20mA endpoints");
            byte[] frame = new byte[31];
            frame[0] = 0x50; frame[1] = 3; frame[2] = 26;
            BinaryPrimitives.WriteInt16BigEndian(frame.AsSpan(3), -16384);
            BinaryPrimitives.WriteInt16BigEndian(frame.AsSpan(9), 16384);
            BinaryPrimitives.WriteInt16BigEndian(frame.AsSpan(15), -16384);
            BinaryPrimitives.WriteUInt16LittleEndian(frame.AsSpan(29), SerialSensors.Crc(frame.AsSpan(0, 29)));
            var imu = SerialSensors.ParseImu(frame);
            Check(Math.Abs(imu.Acc.X + 8 * 9.80665) < 1e-9 && imu.Gyro.X == 1000 && imu.Angle.X == -90, "IMU signed conversion");
            frame[5] ^= 1;
            bool rejected = false;
            try { SerialSensors.ParseImu(frame); } catch (InvalidDataException) { rejected = true; }
            Check(rejected, "IMU bad CRC");
            // Bosch compensation example: adc_P=415148, t_fine=128422.
            double pressure = Bme280Sensor.CompensatePressure(415148, 128422,
                [36477, -10685, 3024, 2855, 140, -7, 15500, -14600, 6000]);
            Check(Math.Abs(pressure - 1006.5326) < 0.01, "BME pressure reference");
            Check(Bme280Sensor.CompensateHumidity(0, 76800, [0, 65536, 0, 1, 0, 0]) == 0, "humidity lower clamp");
            Console.WriteLine("PASS: CRC, GPS parsing, analog scaling, IMU mapping, BME compensation (hardware not tested)");
            return 0;
        }
        catch (Exception ex) { Console.Error.WriteLine(ex); return 1; }
    }
    private static void Check(bool condition, string label)
    {
        if (!condition) throw new Exception($"FAIL: {label}");
    }
}
