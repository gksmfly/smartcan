# SmartCan (Mobile Programming Final)

Android 앱이 모니터링, 제어(오차보정), 데이터소스 전환(LOCAL/FIREBASE/SERVER)을 담당하고, 서버/장비/대시보드는 앱 기능을 확장하는 형태로 설계했다.

- **LOCAL**: SQLite
- **FIREBASE**: Firestore  
- **SERVER**: FastAPI + Neon(PostgreSQL)  
- **확장**: WebSocket 관리자 관제(`/admin`), Grafana 운영 대시보드

---

## 전체 파이프라인

아두이노가 RFID 태깅으로 이벤트를 발생시키면 서버(FastAPI)가 이를 수신해 Neon(PostgreSQL)에 기록한다. 서버는 LSTM, SPC, CUSUM, R2R로 오차를 감지하고 보정하며, 이 과정은 WebSocket(`/admin`)으로 실시간 스트리밍되고 Grafana에서 지표로 집계된다. Android 앱은 LOCAL(SQLite), FIREBASE(Firestore), SERVER(REST) 모드로 이를 조회하고 모니터링한다.

---

## Android 앱이 중심인 이유

SmartCan은 서버와 하드웨어가 있는 프로젝트지만, 사용자가 실제로 조작하고 확인하는 중심은 Android 앱이다.

앱이 제공하는 기능:
1. **모드 전환(LOCAL/FIREBASE/SERVER)**: 1·2·3단계를 앱 한 곳에서 확인할 수 있다.
2. **실시간 모니터링 UI**: 알람, 상태, SPC 결과를 앱 화면에서 즉시 확인한다.
3. **제어(오차보정 버튼)**: 사용자가 앱에서 보정 요청하면 장비 LED가 빨강(ERR)에서 초록(OK)으로 바뀌며 효과를 눈으로 확인한다.

---

## 단계별 구현 (1/2/3단계)

### 1단계 — LOCAL: SQLite
- Android 앱이 SQLite로 저장하고 조회한다.
- 오프라인에서도 동작한다.

### 2단계 — FIREBASE: Firestore
- Android 앱이 Firestore에 저장하고 조회하며 실시간 갱신된다.
- 앱 설정으로 LOCAL과 FIREBASE 간에 전환할 수 있다.

### 3단계 — SERVER: FastAPI + Neon(PostgreSQL)
- Android 앱이 REST로 서버와 통신한다.
- 서버는 Neon(PostgreSQL)에 저장하고 조회한다.
- 서버는 명령어만으로 독립적으로 실행할 수 있다.

---

## 앱 화면 구성

발표와 시연은 다음 3개 화면 중심으로 진행한다.

### Dashboard (모니터링)
- 현재 SKU와 라인 상태
- 최근 알람 리스트(WARN/ERR)
- 최근 충진 결과(목표/실측, OK/ERR)

### Control (제어)
- 오차보정 버튼
- 목표량/레시피(SKU) 설정

### Settings (모드 전환)
- DataSource: LOCAL / FIREBASE / SERVER
- 현재 모드 표시

---

## SmartCan의 핵심: 자동 오류 보정

SmartCan의 차별점은 기록과 조회가 아니라 충진 오차를 감지하고 자동으로 보정 루프를 돈다는 점이다.

- **LSTM**: SKU와 이력을 기반으로 밸브 시간을 추정한다.
- **SPC(관리도)**: 공정 분산과 허용오차를 기반으로 이상을 판단한다.
- **CUSUM**: 누적 변화로 드리프트를 조기에 감지한다.
- **R2R(Run-to-Run)**: 직전 결과를 반영해 다음 사이클 보정값을 적용한다.
- **알람**: 이상 감지 시 DB에 저장하고 관리자에게 즉시 푸시하며 Grafana에서 추이와 빈도를 확인한다.

---

## 실행 흐름

1. **(장비/UNO)** RFID 태깅으로 SKU를 결정하고 `can_in` 이벤트를 전송한다.
2. **(브리지/esp_bridge.py)** 시리얼을 읽어 `line1/event/can_in`을 MQTT에 발행한다.
3. **(서버/FastAPI)** `can_in`을 수신하고 LSTM/R2R로 다음 밸브 시간을 계산해 Neon DB에 기록하고 WebSocket으로 푸시한다.
4. **(장비/UNO)** 충진을 수행하고 `fill_result` 이벤트를 전송한다(실제량/목표량/OK·ERR 포함).
5. **(서버/FastAPI)** `fill_result`를 수신하고 DB에 기록한 뒤 SPC/CUSUM으로 이상을 감지해 알람을 생성하고 WebSocket으로 푸시한다.
6. **(Android 앱)** 사용자가 오차보정 버튼을 클릭하면 서버로 보정 요청을 보낸다.
7. **(서버/FastAPI)** 보정값을 산출하고 기록한 뒤 `CORR` 명령을 발행하고 WebSocket으로 푸시한다.
8. **(장비/UNO)** `CORR`을 수신하고 LED를 빨강(ERR)에서 초록(OK)으로 전환한다.
9. **(관리자)** `/admin`에서 WebSocket 실시간 로그를 확인하고 Grafana에서 알람과 지표 추이를 확인한다.

---

## 레포 구조

```
smartcan/
  arduino/           # UNO 스케치 (RFID/밸브/LED/LCD/7세그)
  backend/           # FastAPI 서버 (3단계)
  dashboard-app/     # Android 앱 (LOCAL/FIREBASE/SERVER 전환)
  infra/             # 로컬 개발용 docker (Postgres/MQTT/Grafana)
  esp_bridge.py      # UNO 시리얼 ↔ MQTT 브리지
  README.md
```

---

## 실행 방법

### Backend 실행 (FastAPI)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Health check: `GET /health`  
API 문서: `GET /docs`

### 환경변수 설정 (.env)

`backend/.env.example`을 `backend/.env`로 복사하고 수정한다.

```env
#SQLite
#FIREBASE
DATABASE_URL=postgresql://<NEON_USER>:<NEON_PASSWORD>@<NEON_HOST>/<NEON_DB>?sslmode=require
SERVER_PORT=8000

# MQTT
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
```

주의: `.env`는 커밋하지 않는다.

### Android 실행 (Android Studio)

`dashboard-app/`을 Android Studio로 열고 Run한다.

#### 모드 전환

`dashboard-app/app/build.gradle.kts`에서 `DATA_SOURCE` 값을 변경한다.

- `"\"LOCAL\""`     // 1단계: SQLite  
- `"\"FIREBASE\""`  // 2단계: Firebase(Firestore)  
- `"\"SERVER\""`    // 3단계: FastAPI + PostgreSQL(Neon)

변경 후 반드시 상단의 `Sync Now`를 클릭해야 적용된다.

**SERVER 모드 주소**
- 에뮬레이터: `http://10.0.2.2:8000` (호스트 PC의 localhost)
- 실기기(같은 Wi-Fi): `http://<PC 로컬 IP>:8000`

**FIREBASE 모드**
- `google-services.json`과 Firestore 설정이 필요하다.

---

## DB 초기화

### LOCAL (SQLite)
앱을 삭제하고 재설치하거나 앱 데이터를 삭제한다.

### FIREBASE (Firestore)
Firebase Console에서 테스트 컬렉션을 삭제하거나 테스트 프로젝트를 분리한다.

### SERVER (Neon PostgreSQL)
Neon Branch를 새로 생성하거나 스키마를 초기화한다(데이터 전체 삭제 주의).

### 로컬 Docker 초기화 (선택)
```bash
cd infra
docker compose down -v
docker compose up -d
```

---

## 3단계 REST/WebSocket 인터페이스

Base URL: `http://<server-host>:8000`

기본 엔드포인트:
- `GET /health`
- `GET /docs`
- `GET /admin`
- `WS /ws/admin`

API 예시:
- `GET/POST /api/v1/alarms`
- `GET/POST /api/v1/spc/states`
- `GET/POST /api/v1/cycles`
- `POST /api/v1/control/fill`
- `POST /api/v1/control/corr` (앱 오차보정 버튼과 연결)

---

## Arduino (UNO) 로직

- RFID UID를 SKU에 매핑한다(COKE_355 / CIDER_500).
- Changeover 감지 시 노랑 LED를 표시한다.
- Changeover 직후 다음 태깅에서 BAD FILL이 발생하면 빨강 LED를 표시하고 `fill_result(ERR)`을 전송한다.
- 앱에서 오차보정 버튼을 누르면 서버가 `CORR`을 발행하고 UNO LED가 빨강에서 초록으로 전환된다.

---

## Grafana (운영 대시보드)

데이터 소스: Neon(PostgreSQL)

패널:
- 라인 상태
- 알람 빈도
- 오차율
- 모델 지표

권한:
- Folder: `Admin Dashboard`
- Teams: `ops-admin(Edit)`, `ops-viewer(View)`

---

## 빠른 시연 시나리오

1. 앱 Settings에서 LOCAL ↔ FIREBASE ↔ SERVER를 전환해 1·2·3단계를 확인한다.
2. Dashboard에서 알람과 상태를 확인한다.
3. BAD FILL을 유도해 빨강 LED를 표시한 뒤 앱에서 오차보정 버튼을 누르면 LED가 빨강에서 초록으로 전환되는 것을 확인한다.
4. 관리자 `/admin`에서 실시간 로그를 확인하고 Grafana 지표로 운영까지 확장해 보여준다.
