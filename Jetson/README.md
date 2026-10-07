# Jetson 센서 관측 UI

`tcp_server.py`가 Raspberry Pi의 TCP JSON을 수신하고 데이터 API와 React 빌드 파일을 제공합니다.
기존 `dashboard.html`은 React 앱(`ui/src`)으로 대체했습니다.

## 운영 실행

저장소 루트에서 실행합니다. UI를 처음 설치하거나 수정한 뒤에는 먼저 빌드해야 합니다.

```bash
cd Jetson/ui
pnpm install --frozen-lockfile
pnpm build
cd ../..
python3 Jetson/tcp_server.py
```

- 빌드 환경: Node.js 22.12 이상(22 LTS 또는 24 LTS 권장), pnpm 11.
- Node와 pnpm은 UI 빌드 때만 필요합니다. 이미 빌드한 `Jetson/ui/dist`가 있으면 운영 시에는 Python만 실행합니다.
- Jetson OS에서 최신 Node 실행이 어려우면 노트북에서 빌드하고 `dist` 폴더 전체를 Jetson의 `Jetson/ui/dist`로 복사할 수 있습니다. `node_modules`는 복사하지 않습니다.
- `dist`, `node_modules`는 Git에 포함하지 않습니다. `git pull`만으로 새 UI 빌드가 생성되지는 않습니다.
- UI: `http://<Jetson IP>:8080` / TCP 수신: 5000 / API: `/api/data?after=0`.
- 외부 CDN이나 폰트 다운로드 없이 로컬 파일로 동작합니다.
- 빌드 파일이 없으면 UI 요청에 503과 빌드 안내를 반환합니다. TCP/API는 계속 동작합니다.
- 포트와 빌드 경로 변경: `--port`, `--web-port`, `--ui-dir`.

## 노트북에서 개발

터미널 1 (저장소 루트):
```bash
python Jetson/tcp_server.py
```

터미널 2:
```bash
cd Jetson/ui
pnpm install --frozen-lockfile
pnpm dev
```

브라우저에서 `http://localhost:5173`을 엽니다. Vite가 `/api` 요청을 `127.0.0.1:8080`으로 전달합니다.
실제 센서가 연결되지 않으면 수신 대기 화면이 표시되며 가짜 수치는 생성하지 않습니다.

## 화면과 데이터

- **실시간 관측**: 예측 적설 높이, CT100 노면 온도, FTM02 온도·습도, BME280 기압(hPa), 시간별 그래프.
- **센서 진단**: 예측 실패/이력 수집 상태, 수신 간격, 회차 시작부터 전송 데이터 생성까지의 시간, 센서 읽기 시간과 형식 오류.
- **수신 기록**: 최근 1시간/최대 3,600건, 상태 필터, 페이지 조회, CSV 다운로드.
- 저장은 기존처럼 메모리 방식입니다. 서버 재시작 시 초기화되며 CSV는 브라우저가 받은 기록을 내보냅니다. 장기 저장 DB는 포함하지 않습니다.
- 수신 중단 3초 후 현재 수치는 `—`로 바뀝니다. 과거 그래프/기록은 유지합니다. 0과 누락값은 구분합니다.
- 현재 기본 송신 설정의 가상 거리·속도를 시험 운전 안내로 표시합니다.
- IMU 원시 값, 실제 ML 세부 시간, GPS 지도는 현재 전송 형식에 없으므로 표시하지 않습니다.
- 기존 Raspberry Pi 코드와 호환되며 이번 UI 변경에 Pi 수정은 필요하지 않습니다.

## 검증

```bash
python -m unittest Jetson.test_tcp_server
cd Jetson/ui
pnpm test
pnpm build
```

인증 기능은 없는 로컬 관측용 서버입니다. 기존처럼 장비 내부망에서 사용합니다.
