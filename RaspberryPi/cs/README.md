# C# 센서 수집 시간 측정

`../python/benchmark_sensors.py`와 비교하기 위한 .NET 8 콘솔 프로그램입니다.
TCP 전송 없이 **수집 시간**, **센서 데이터** 두 영역을 출력합니다.
노트북의 .NET 10 SDK로 개발해도 프로젝트 대상은 `net8.0`으로 유지합니다.

## Raspberry Pi 실행

Pi에는 .NET 8 SDK, 기존 `megaind`, I²C/시리얼 장치 접근 권한이 필요합니다.
Python 측정 프로그램과 동시에 실행하지 마세요.

일반적인 실행 (프로젝트 루트에서):

```bash
dotnet run --project RaspberryPi/cs/SensorBenchmark.csproj -c Release
```

현재 장비는 내부 저장소가 가득 차 있으므로 **SD카드 ext4 공간에서 빌드**하세요.
아래 명령은 앞서 만든 `/mnt/dotnet-dev`, `/tmp/.dotnet` 마운트와
`DOTNET_ROOT`, `DOTNET_CLI_HOME`, `TMPDIR`, `NUGET_PACKAGES` 설정이 유효한 상태를 전제로 합니다.
마운트는 현재 재부팅 시 자동 복구되지 않습니다.

Git으로 변경 사항을 받은 다음, C# 소스를 SD카드로 복사해 실행합니다.
두 번째 실행부터도 최신 소스를 다시 복사하세요. 기존 저장소 파일은 이동하지 않습니다.

```bash
mountpoint /mnt/dotnet-dev
mountpoint /tmp/.dotnet
mkdir -p /mnt/dotnet-dev/projects/SensorBenchmark
cp "$HOME/Projects/Road_Surface/RaspberryPi/cs/"*.cs \
   "$HOME/Projects/Road_Surface/RaspberryPi/cs/"*.csproj \
   /mnt/dotnet-dev/projects/SensorBenchmark/
dotnet run --project /mnt/dotnet-dev/projects/SensorBenchmark/SensorBenchmark.csproj -c Release
```

Ctrl+C로 종료합니다. 한 번만 수집하려면 뒤에 `-- --once`를 붙입니다.
하드웨어 없이 파서/보정 계산만 검증하려면 `-- --self-test`를 붙입니다.
프로젝트 생성이나 .NET 10을 강제하는 `global.json`은 필요하지 않습니다.

## 측정 조건

| 센서 | Python과 맞춘 조건 |
| --- | --- |
| CT100 | `megaind 0 iinrd 1`, 2초 제한, 4–20mA → -20–100°C |
| FTM02 | `megaind 0 uinrd 1`, `megaind 0 uinrd 2` 순서, 각각 2초 제한 |
| BME280 | I²C bus 1, 주소 0x76, 온도 x1 / 습도 x1 / 압력 x16, 필터 off, forced mode |
| GPS | `/dev/ttyUSB0`, 4800 baud, 8N1, GPGGA/GNGGA, 읽기 제한 0.2초, 전체 약 1초 |
| IMU | `/dev/ttyUSB1`, 9600 baud, 8N1, slave 0x50, 0x003A부터 13개 레지스터, 31바이트, 0.5초 제한 |

포트와 I²C bus는 환경 변수 `GPS_PORT`, `IMU_PORT`, `BME_I2C_BUS`로 변경할 수 있습니다.
`board.I2C()`가 실제로 bus 1을 쓰는지 Pi 환경에서 확인해야 합니다.

- 순서는 CT100 → FTM02 → BME280 → GPS → IMU입니다.
- `Stopwatch`로 실제 read 호출과 응답 검증·변환 시간을 측정합니다.
- 화면 출력과 수집 뒤 1초 대기는 측정에서 제외합니다. 전체 시간에는 각 센서 측정 래퍼의 작은 비용도 포함됩니다.
- 첫 회에는 포트 연결·BME 초기화·JIT 비용이 포함됩니다. 반복 비교 시 준비 실행을 제외하세요.
- 실패 시간은 타임아웃/예외 처리 포함이며 정상 수집 평균에 섞지 마세요.
- GPS 문장 수신과 위치 Fix는 별도입니다. 버퍼에 남은 과거 문장을 읽는 시간일 수 있습니다.
- C# 오류 메시지는 측정 후 출력합니다. Python read()는 오류를 내부에서 출력하므로 실패 경로의 시간은 엄밀히 동일하지 않습니다.
- 시리얼 드라이버/스케줄링 차이로 타임아웃 경계가 조금 달라질 수 있습니다.

## BME280 비교 시 주의

Adafruit `basic.py` 2.6.4의 기본값 및 측정 순서를 기준으로 했습니다.
Python 코드가 온도·습도·기압 속성을 차례로 접근하면 **각 속성마다 별도 변환**이 일어나므로
C#도 세 번 측정합니다. 한 번 측정 후 세 값을 재사용하는 최적화는 하지 않았습니다.
Pi에 설치된 라이브러리 버전/설정이 다르면 시간이 달라질 수 있습니다.

```bash
python3 -m pip show adafruit-circuitpython-bme280
```

출처: https://github.com/adafruit/Adafruit_CircuitPython_BME280/blob/main/adafruit_bme280/basic.py
보정식 출처/라이선스는 `THIRD_PARTY_NOTICES.md`에 있습니다.

## IMU 값 해석

Python의 레지스터 매핑·바이트 순서·변환 계수를 그대로 사용합니다.
앞서 정지 상태에서 큰 가속도/각속도가 나왔다면 하드웨어 설정 및 레지스터 매핑을 별도로 검증해야 합니다.
CRC 통과는 데이터 내용의 물리적 타당성을 보장하지 않습니다.

## 검증 범위

`--self-test`는 알려진 Modbus CRC, GGA 좌표/체크섬/Fix 없음, 아날로그 변환,
IMU signed 값/잘못된 CRC, BME 보정식을 검증합니다.
실제 I²C/시리얼 입출력, GPIO 권한, 센서 측정 시간은 Pi에서 확인해야 합니다.
