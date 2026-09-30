using System.Buffers.Binary;
using System.Diagnostics;
using System.Globalization;
using System.IO.Ports;
using System.Text;

namespace SensorBenchmark;

public record CtData(double Temperature, double Current);
public record FtmData(double HumidityVoltage, double TemperatureVoltage, double Humidity, double Temperature);
public record BmeData(double Temperature, double Humidity, double Pressure);
public record GpsData(bool Fix, double? Latitude, double? Longitude, double? Altitude, int Satellites, int Quality);
public record Vector(double X, double Y, double Z);
public record ImuData(Vector Acc, Vector Gyro, Vector Angle);

public static class AnalogSensors
{
    public static double CurrentToTemperature(double value) => -20 + (value - 4) / 16 * 120;
    public static CtData ReadCt()
    {
        double current = ReadChannel("iinrd", 1);
        return new(CurrentToTemperature(current), current);
    }

    public static FtmData ReadFtm()
    {
        double humidity = ReadChannel("uinrd", 1);
        double temperature = ReadChannel("uinrd", 2);
        return new(humidity, temperature, humidity * 10, -20 + temperature * 10);
    }

    private static double ReadChannel(string operation, int channel)
    {
        var info = new ProcessStartInfo("megaind")
        {
            RedirectStandardOutput = true, RedirectStandardError = true,
            UseShellExecute = false, CreateNoWindow = true
        };
        info.ArgumentList.Add("0");
        info.ArgumentList.Add(operation);
        info.ArgumentList.Add(channel.ToString(CultureInfo.InvariantCulture));
        using var process = Process.Start(info) ?? throw new IOException("megaind 실행 실패");
        // Drain both streams concurrently to avoid a full pipe blocking the process.
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        if (!process.WaitForExit(2000))
        {
            process.Kill(entireProcessTree: true);
            process.WaitForExit();
            throw new TimeoutException("megaind 응답 제한 2초 초과");
        }
        string output = stdout.GetAwaiter().GetResult();
        string error = stderr.GetAwaiter().GetResult();
        if (process.ExitCode != 0) throw new IOException($"megaind: {error.Trim()}");
        double value = double.Parse(output.Trim(), CultureInfo.InvariantCulture);
        if (!double.IsFinite(value)) throw new InvalidDataException("유효하지 않은 아날로그 값");
        return value;
    }
}

public sealed class SerialSensors : IDisposable
{
    private SerialPort? gps, imu;
    private static SerialPort Open(string path, int baud, int timeout)
    {
        var port = new SerialPort(path, baud, Parity.None, 8, StopBits.One)
        {
            ReadTimeout = timeout, WriteTimeout = 500, Handshake = Handshake.None,
            DtrEnable = true, RtsEnable = true
        };
        try { port.Open(); return port; }
        catch { port.Dispose(); throw; }
    }

    public GpsData ReadGps()
    {
        gps ??= Open(Environment.GetEnvironmentVariable("GPS_PORT") ?? "/dev/ttyUSB0", 4800, 200);
        var elapsed = Stopwatch.StartNew();
        while (elapsed.Elapsed.TotalSeconds < 1)
        {
            // Like pyserial.readline(), retain a partial line on a read timeout.
            var line = new StringBuilder();
            while (line.Length < 1024 && elapsed.Elapsed.TotalSeconds < 1.2)
            {
                int value;
                try { value = gps.ReadByte(); }
                catch (TimeoutException) { break; }
                if (value == '\n') break;
                if (value < 128) line.Append((char)value);
            }
            var result = ParseGga(line.ToString().Trim());
            if (result is not null) return result;
        }
        throw new TimeoutException("GPS GGA 수신 없음 (1초 대기, 시리얼 읽기 제한 0.2초)");
    }

    public static GpsData? ParseGga(string line)
    {
        if (!line.StartsWith("$GPGGA,") && !line.StartsWith("$GNGGA,")) return null;
        int star = line.IndexOf('*');
        if (star >= 0)
        {
            if (line.Length != star + 3 || !byte.TryParse(line.AsSpan(star + 1),
                    NumberStyles.HexNumber, CultureInfo.InvariantCulture, out byte expected)) return null;
            byte checksum = 0;
            foreach (char c in line.AsSpan(1, star - 1)) checksum ^= (byte)c;
            if (checksum != expected) return null;
            line = line[..star];
        }
        // pynmea2.parse defaults to allowing sentences without a checksum.
        var fields = line.Split(',');
        if (fields.Length < 10) return null;
        try
        {
            int quality = int.Parse(fields[6].Length == 0 ? "0" : fields[6], CultureInfo.InvariantCulture);
            int satellites = int.Parse(fields[7].Length == 0 ? "0" : fields[7], CultureInfo.InvariantCulture);
            if (quality == 0) return new(false, null, null, null, satellites, quality);
            return new(true, Coordinate(fields[2], fields[3]), Coordinate(fields[4], fields[5]),
                double.Parse(fields[9].Length == 0 ? "0" : fields[9], CultureInfo.InvariantCulture), satellites, quality);
        }
        catch (FormatException) { return null; }
        catch (OverflowException) { return null; }
    }

    private static double Coordinate(string value, string direction)
    {
        if (value.Length == 0) return 0;
        double raw = double.Parse(value, CultureInfo.InvariantCulture);
        double degrees = Math.Floor(raw / 100);
        return (degrees + (raw - degrees * 100) / 60) * (direction is "S" or "W" ? -1 : 1);
    }

    public ImuData ReadImu()
    {
        imu ??= Open(Environment.GetEnvironmentVariable("IMU_PORT") ?? "/dev/ttyUSB1", 9600, 500);
        byte[] command = [0x50, 0x03, 0, 0x3A, 0, 13, 0, 0];
        BinaryPrimitives.WriteUInt16LittleEndian(command.AsSpan(6), Crc(command.AsSpan(0, 6)));
        imu.DiscardInBuffer();
        imu.Write(command, 0, command.Length);
        imu.BaseStream.Flush();
        byte[] response = new byte[31];
        int received = 0;
        var timer = Stopwatch.StartNew();
        while (received < response.Length)
        {
            int remaining = 500 - (int)timer.ElapsedMilliseconds;
            if (remaining <= 0) throw new TimeoutException($"IMU 응답 길이 {received}/31");
            imu.ReadTimeout = remaining;
            received += imu.Read(response, received, response.Length - received);
        }
        return ParseImu(response);
    }

    public static ushort Crc(ReadOnlySpan<byte> data)
    {
        ushort crc = 0xFFFF;
        foreach (byte value in data)
        {
            crc ^= value;
            for (int bit = 0; bit < 8; bit++)
                crc = (ushort)((crc & 1) != 0 ? (crc >> 1) ^ 0xA001 : crc >> 1);
        }
        return crc;
    }

    public static ImuData ParseImu(byte[] response)
    {
        if (response.Length != 31 || response[0] != 0x50 || response[1] != 3 || response[2] != 26)
            throw new InvalidDataException("IMU 주소/기능/응답 길이 불일치");
        if (Crc(response.AsSpan(0, 29)) != BinaryPrimitives.ReadUInt16LittleEndian(response.AsSpan(29)))
            throw new InvalidDataException("IMU CRC 불일치");
        // Preserve Python's register mapping and byte order for the baseline comparison.
        double Raw(int index) => BinaryPrimitives.ReadInt16BigEndian(response.AsSpan(3 + index * 2, 2)) / 32768.0;
        return new(new(Raw(0) * 16 * 9.80665, Raw(1) * 16 * 9.80665, Raw(2) * 16 * 9.80665),
            new(Raw(3) * 2000, Raw(4) * 2000, Raw(5) * 2000),
            new(Raw(6) * 180, Raw(7) * 180, Raw(8) * 180));
    }

    public void Dispose()
    {
        try { gps?.Dispose(); }
        finally { imu?.Dispose(); }
    }
}
