# SmartCan Backend (3단계 + Option C)

## 3단계 목표
- 서버 단독 실행 가능
- 서버가 DB에 연결되어 데이터(사이클/알람/SPC 상태)를 저장
- Android ↔ 서버 통신(REST)

## Option C 목표
- 관리자 실시간 대시보드: REST + WebSocket
- WS `/ws/admin`로 실시간 이벤트(push)
- 최소 대시보드: `/admin` 한 페이지로 실시간 로그 확인

---

## 폴더
- `app/`: FastAPI 앱
- `models/`: 학습된 모델 파일
- `.env.example`: 환경변수 예시

---

## 로컬 실행 (명령어만으로 실행)

### 1) (권장) infra의 docker로 DB+MQTT 올리기
레포 루트 기준:

```bash
cd infra
docker compose up -d
```

그리고 `backend/.env`에 DB 주소를 로컬 Postgres로 설정:

```env
DATABASE_URL=postgresql://smartcan:1234@localhost:5432/smartcan
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
```

### 2) backend 실행
```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt

# 환경변수 준비
# (처음엔 .env.example을 복사해서 .env로 사용 권장)

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: `GET /health`
- Swagger: `GET /docs`

---

## 관리자 실시간 대시보드(Option C)

- 페이지: `GET /admin`
- WebSocket: `ws://localhost:8000/ws/admin`

WS에서 내려오는 이벤트 예:
- `type=can_in`
- `type=fill_requested`
- `type=fill_result`
- `type=spc_state`
- `type=alarm`
- `type=corr_issued`

---

## MQTT 연동(서버 ↔ 장비)

- 서버는 MQTT를 구독해서 UNO 이벤트를 DB에 기록하고, 필요 시 다시 명령을 publish 함.

### Subscribe (장비 → 서버)
- `line1/event/can_in`
- `line1/event/fill_result`

### Publish (서버 → 장비)
- `line1/cmd/fill`
- `line1/cmd/corr`

---

## 실행 흐름 요약
1. (장비) RFID 태깅 → `can_in` 이벤트 publish
2. (서버) `can_in` 수신 → 다음 밸브시간 계산 → `cmd/fill` publish + DB 기록 + WS push
3. (장비) Fill 수행 → `fill_result` publish
4. (서버) `fill_result` 수신 → DB 기록 + SPC 계산 + 알람 생성 + WS push
5. (관리자) `/admin`에서 WS로 실시간 확인
