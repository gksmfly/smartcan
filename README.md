# SmartCan (Mobile Programming Final)
**핵심:** Android 앱이 **모니터링 + 제어(오차보정) + 데이터소스 전환(LOCAL/FIREBASE/SERVER)** 을 담당하고,  
서버/장비/대시보드는 앱 기능을 **확장(3단계)** 하는 형태로 설계했다.

- **LOCAL**: SQLite
- **FIREBASE**: Firestore  
- **SERVER**: FastAPI + Neon(PostgreSQL)  
- **확장**: WebSocket 관리자 관제(`/admin`), Grafana 운영 대시보드(Neon 기반)

---

## 0) 전체 파이프라인
아두이노( RFID 태깅→충진 수행/결과 전송 )가 이벤트를 서버(FastAPI)로 보내면 서버가 Neon(PostgreSQL)에 기록하면서 LSTM·SPC·CUSUM·R2R로 오차를 감지/보정해 다음 충진 명령을 내려주고, 그 과정이 WebSocket(/admin)으로 실시간 스트리밍되며 Grafana에서 지표로 집계되고 Android 앱은 LOCAL(SQLite)/FIREBASE(Firestore)/SERVER(REST) 모드로 이를 조회·모니터링한다.

---

## 1) “모바일 앱”이 중심인 이유
SmartCan은 서버/하드웨어가 있는 프로젝트지만, **사용자가 실제로 조작·확인하는 중심은 Android 앱**이다.

앱이 하는 일:
1. **모드 전환(LOCAL/FIREBASE/SERVER)**: 1·2·3단계를 앱 한 곳에서 체감 가능  
2. **실시간 모니터링 UI**: 알람/상태/SPC 결과를 앱 화면에서 즉시 확인  
3. **제어(오차보정 버튼)**: 사용자가 앱에서 보정 요청 → 장비 LED가 **빨강(ERR) → 초록(OK)** 으로 바뀌며 효과가 “눈으로” 증명됨  

---

## 2) 단계별 구현 매핑 (1/2/3단계)
### 1단계(필수) — LOCAL: SQLite
- Android 앱이 **SQLite** 로 저장/조회
- 오프라인에서도 동작

### 2단계 — FIREBASE: Firestore
- Android 앱이 **Firestore**에 저장/조회 및 실시간 갱신(리스너)
- 앱 설정(또는 빌드 설정)으로 **LOCAL ↔ FIREBASE** 전환 가능

### 3단계 — SERVER: FastAPI + Neon(PostgreSQL)
- Android 앱이 **REST로 서버 통신**
- 서버는 **Neon(PostgreSQL)** 에 저장/조회
- 서버는 **명령어만으로 단독 실행 가능**

---

## 3) 앱 화면 구성(권장 시연 흐름)
> “앱이 약해 보이지 않게” 발표/시연은 아래 3화면 중심으로 진행한다.

### 3.1 Dashboard(모니터링)
- 현재 SKU/라인 상태
- 최근 알람 리스트(WARN/ERR)
- 최근 충진 결과(목표/실측, OK/ERR)

### 3.2 Control(제어)
- **오차보정 버튼**(핵심)
- 목표량/레시피(SKU) 설정

### 3.3 Settings(모드 전환)
- DataSource: `LOCAL / FIREBASE / SERVER`
- 현재 모드 배지 표시(시연 증명용)

---

## 4) SmartCan의 핵심 장점: “자동 오류 보정”
SmartCan의 차별점은 “기록/조회”가 아니라, **충진 오차를 감지하고 자동 보정 루프를 돌린다**는 점이다.

- **LSTM**: SKU/이력 기반 밸브시간(Valve time) 추정
- **SPC(관리도)**: 공정 분산/허용오차 기반 이상 판단
- **CUSUM**: 누적 변화로 드리프트 조기 감지(예: NEG_DRIFT)
- **R2R(Run-to-Run)**: 직전 결과를 반영해 다음 사이클 보정값 적용
- **알람/전파**: 이상 감지 시 DB 저장 + 관리자(WebSocket) 즉시 push + Grafana에서 추이/빈도 확인

---

## 5) 실행 흐름 요약(앱 “보정 버튼” 포함, 내 프로젝트 기준)
1. **(장비/UNO)** RFID 태깅 → SKU 결정 → `can_in` 이벤트 전송(시리얼 `P:line1/event/can_in:{...}`)
2. **(브리지/esp_bridge.py)** 시리얼을 읽어 `line1/event/can_in`을 MQTT publish
3. **(서버/FastAPI)** `can_in` 수신 → 다음 밸브시간(valve_ms) 계산(LSTM/R2R) → **Neon DB 기록** + **WS push** + (필요 시) 충진 명령 발행
4. **(장비/UNO)** 충진 수행 → `fill_result` 이벤트 전송(실제량/목표량/OK·ERR 포함)
5. **(서버/FastAPI)** `fill_result` 수신 → DB 기록 → SPC/CUSUM로 이상 감지 → 알람 생성 + WS push
6. **(Android 앱)** 사용자가 **오차보정 버튼** 클릭 → 서버로 보정 요청(REST)
7. **(서버/FastAPI)** 보정값 산출/기록(R2R/ML) → `CORR` 명령 발행 + WS push
8. **(장비/UNO)** `CORR` 수신 → 보정 상태 표시 후 **LED가 빨강(ERR)에서 초록(OK)으로 전환**
9. **(관리자)** `/admin`에서 WS 실시간 확인 + Grafana에서 알람/지표 추이 확인

---

## 6) 레포 구조
```
smartcan/
  arduino/           # UNO 스케치( RFID/밸브/LED/LCD/7세그 )
  backend/           # FastAPI 서버(3단계)
  dashboard-app/     # Android 앱(LOCAL/FIREBASE/SERVER 전환)
  infra/             # 로컬 개발용 docker(Postgres/MQTT/Grafana 등)
  esp_bridge.py      # UNO 시리얼 ↔ MQTT 브리지
  README.md
```

---

## 7) 실행 방법 ✅ (평가자 기준 “바로 실행”)
### 7.1 Backend 실행(FastAPI)
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
- Health: `GET /health`
- Swagger(API): `GET /docs`

### 7.2 환경변수(.env) 예시
`backend/.env.example` → `backend/.env` 복사 후 수정
```env
#SQLite
#FIREBASE
DATABASE_URL=postgresql://<NEON_USER>:<NEON_PASSWORD>@<NEON_HOST>/<NEON_DB>?sslmode=require
SERVER_PORT=8000

# MQTT
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
```
> ⚠️ `.env`는 커밋하지 않는다.

### 7.3 Android 실행(Android Studio)
- `dashboard-app/`을 Android Studio로 열고 Run

#### 모드 전환 방법(필수)
`dashboard-app/app/build.gradle.kts`에서 단계별 `DATA_SOURCE` 값을 바꾸면 된다.

- `"\"LOCAL\""`     // 1단계: SQLite  
- `"\"FIREBASE\""`  // 2단계: Firebase(Firestore)  
- `"\"SERVER\""`    // 3단계: FastAPI + PostgreSQL(Neon)

✅ 변경 후 **상단의 `Sync Now`는 반드시 클릭**해야 적용된다.

**SERVER 모드 주소(중요)**
- 에뮬레이터: `http://10.0.2.2:8000` (호스트 PC의 localhost)
- 실기기(같은 Wi-Fi): `http://<PC 로컬 IP>:8000`

**FIREBASE 모드**
- `google-services.json` 및 Firestore 설정 필요

---

## 8) DB 초기화(모드별)
### 8.1 LOCAL(SQLite)
- 앱 삭제/재설치 또는 앱 데이터 삭제

### 8.2 FIREBASE(Firestore)
- Firebase Console에서 테스트 컬렉션 삭제(또는 테스트 프로젝트 분리)

### 8.3 SERVER(Neon PostgreSQL)
- (권장) Neon Branch 새로 생성
- 또는 스키마 초기화 후 재생성(데이터 전체 삭제 주의)

### 8.4 (선택) 로컬 Docker 초기화(시연/평가 편의)
```bash
cd infra
docker compose down -v
docker compose up -d
```

---

## 9) 3단계 REST/WS 인터페이스(문서화)
Base URL: `http://<server-host>:8000`

- `GET /health`
- `GET /docs`
- `GET /admin`
- `WS /ws/admin`

(구현 기준 예시)
- `GET/POST /api/v1/alarms`
- `GET/POST /api/v1/spc/states`
- `GET/POST /api/v1/cycles`
- `POST /api/v1/control/fill`
- `POST /api/v1/control/corr`  ← 앱 **오차보정 버튼**과 연결

---

## 10) Arduino(UNO) 데모 로직 요약
- RFID UID → SKU 매핑(COKE_355 / CIDER_500)
- Changeover 감지 시 노랑 LED
- Changeover 직후 다음 태깅에서 BAD FILL(예: 355 vs 344) 발생 → 빨강 LED + `fill_result(ERR)` 전송
- 앱에서 **오차보정 버튼** → 서버가 `CORR` 발행 → UNO LED가 **빨강→초록**으로 전환(보정 효과 시각화)

---

## 11) Grafana(운영 대시보드) & 권한 제어
- 데이터 소스: Neon(PostgreSQL)
- 패널 : 라인 상태 / 알람 빈도 / 오차율 / 모델 지표
- 권한 :
  - Folder: `Admin Dashboard`
  - Teams: `ops-admin(Edit)`, `ops-viewer(View)`

---

## 12) 빠른 시연 시나리오(모바일 중심)
1) 앱 Settings에서 **LOCAL ↔ FIREBASE ↔ SERVER 전환** 시연(1·2·3단계 한 번에 증명)  
2) Dashboard에서 알람/상태 확인  
3) BAD FILL 유도(빨강 LED) → 앱에서 **오차보정 버튼** → LED **빨강→초록** 전환 확인  
4) 관리자 `/admin` 실시간 로그 + Grafana 지표로 “운영”까지 확장 보여주기
