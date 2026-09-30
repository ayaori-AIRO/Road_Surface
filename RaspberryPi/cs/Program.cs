using System.Diagnostics;
using System.Globalization;
using System.Text;
using SensorBenchmark;

Console.OutputEncoding = Encoding.UTF8;
CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;
if (args.Contains("--self-test")) return SelfTest.Run();
if (args.Contains("--help"))
{
    Console.WriteLine("dotnet run -c Release -- [--once | --self-test]\n환경 변수: GPS_PORT, IMU_PORT, BME_I2C_BUS (기본값: /dev/ttyUSB0, /dev/ttyUSB1, 1)");
    return 0;
}
if (args.Any(a => a != "--once")) { Console.Error.WriteLine("지원하지 않는 옵션. --help 참조"); return 2; }
if (!OperatingSystem.IsLinux())
{
    Console.Error.WriteLine("실제 센서 측정은 Linux Raspberry Pi에서 실행하세요. PC 검증: --self-test");
    return 2;
}

using var stopped = new ManualResetEventSlim();
Console.CancelKeyPress += (_, e) => { e.Cancel = true; stopped.Set(); };
using var serial = new SerialSensors();
using var bme = new Bme280Sensor();
Console.WriteLine("센서 수집 시간 측정 / C# .NET 8 / TCP 없음");
Console.WriteLine("순서: CT100 → FTM02 → BME280 → GPS → IMU / 출력·1초 대기 제외 / Ctrl+C 종료");
int iteration = 0;
do
{
    long start = Stopwatch.GetTimestamp();
    var ct = Measure("CT100", () => AnalogSensors.ReadCt());
    var ftm = Measure("FTM02", () => AnalogSensors.ReadFtm());
    var env = Measure("BME280", bme.ReadData);
    var gps = Measure("GPS", serial.ReadGps);
    var imu = Measure("IMU", serial.ReadImu);
    double total = Stopwatch.GetElapsedTime(start).TotalMilliseconds;
    iteration++;

    Console.WriteLine($"\n==============================================\nTIME : {DateTime.Now:yyyy-MM-dd HH:mm:ss} / 측정 {iteration}회");
    if (iteration == 1) Console.WriteLine("첫 회: 센서 연결·초기화 및 JIT 등 초기 실행 비용 포함");
    Console.WriteLine("[ 수집 시간 ]");
    PrintTiming(ct); PrintTiming(ftm); PrintTiming(env); PrintTiming(gps); PrintTiming(imu);
    Console.WriteLine($"전체 수집 시간 : {total:F3} ms ({total / 1000:F6} 초)");
    if (ct.Value is null || ftm.Value is null || env.Value is null || gps.Value is null || imu.Value is null)
        Console.WriteLine("일부 센서 수집 실패: 실패 처리·대기 시간이 포함됩니다.");
    Console.WriteLine("\n[ 센서 데이터 ]\n[ CT-100N-CL420 ]");
    Console.WriteLine(ct.Value is {} c ? $"Temperature : {c.Temperature:F2} °C\nCurrent : {c.Current:F3} mA" : "No Data");
    Console.WriteLine("\n[ BT-FTM02 ]");
    Console.WriteLine(ftm.Value is {} f ? $"Humidity Voltage : {f.HumidityVoltage:F3} V / Humidity : {f.Humidity:F2} %RH\nTemperature Voltage : {f.TemperatureVoltage:F3} V / Temperature : {f.Temperature:F2} °C" : "No Data");
    Console.WriteLine("\n[ BME280 ]");
    Console.WriteLine(env.Value is {} b ? $"Temperature : {b.Temperature:F2} °C\nHumidity : {b.Humidity:F2} %RH\nPressure : {b.Pressure:F2} hPa" : "No Data");
    Console.WriteLine("\n[ BU-353N GPS ]");
    if (gps.Value is {} g)
    {
        Console.WriteLine(g.Fix ? $"Latitude : {g.Latitude:F6}\nLongitude : {g.Longitude:F6}\nAltitude : {g.Altitude:F1} m" : "GPS Fix 없음");
        Console.WriteLine($"Satellites : {g.Satellites}\nQuality : {g.Quality}");
    }
    else Console.WriteLine("GPS 데이터 수신 없음");
    Console.WriteLine("\n[ WT901C485 IMU ]");
    if (imu.Value is {} i)
    {
        Console.WriteLine($"ACC : X={i.Acc.X:F3} Y={i.Acc.Y:F3} Z={i.Acc.Z:F3} m/s²");
        Console.WriteLine($"GYRO : X={i.Gyro.X:F2} Y={i.Gyro.Y:F2} Z={i.Gyro.Z:F2} °/s");
        Console.WriteLine($"ANGLE : Roll={i.Angle.X:F2}° Pitch={i.Angle.Y:F2}° Yaw={i.Angle.Z:F2}°");
    }
    else Console.WriteLine("No Data");
    Console.WriteLine("==============================================");
    if (args.Contains("--once")) break;
} while (!stopped.Wait(1000));
return 0;

static Reading<T> Measure<T>(string name, Func<T> read) where T : class
{
    long start = Stopwatch.GetTimestamp();
    T? value = null;
    string? error = null;
    try { value = read(); }
    catch (Exception ex) { error = ex.Message; }
    return new(name, value, Stopwatch.GetElapsedTime(start).TotalMilliseconds, error);
}

static void PrintTiming<T>(Reading<T> result) where T : class
{
    string status = result.Value is null ? $"수집 실패 / {result.Error}" :
        result.Value is GpsData { Fix: false } ? "수신 성공 / Fix 없음" : "수신 성공";
    Console.WriteLine($"{result.Name,-6} : {result.Milliseconds,10:F3} ms | {status}");
}

record Reading<T>(string Name, T? Value, double Milliseconds, string? Error) where T : class;
