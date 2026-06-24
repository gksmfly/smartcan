# SmartCan: IoT Fill-Level Error Detection and Auto-Correction System

> **TL;DR**: An Android-centered IoT system that detects and corrects filling errors in a smart container line using LSTM valve timing estimation, SPC process control, CUSUM drift detection, and R2R run-to-run correction — with real-time monitoring via WebSocket and Grafana.

---

## Problem Statement

Automated filling systems accumulate small errors over time — valve timing drift, product viscosity changes, mechanical wear — that compound into systematic fill defects if uncorrected.

- Static valve timing settings don't adapt to per-SKU characteristics or gradual mechanical drift
- Post-hoc error detection catches problems after defective units are produced, not before
- Operators need real-time visibility into process state, not just batch-end summaries

---

## Approach

- **LSTM for adaptive valve timing**: Rather than fixed timing per SKU, an LSTM trained on fill history predicts the valve open duration needed for the next cycle, adapting to drift without manual recalibration
- **SPC for statistically grounded alarm thresholds**: Control charts (Shewhart) set alarm boundaries based on process variance — avoiding both false positives from tight tolerances and missed defects from loose ones
- **CUSUM for early drift detection**: Cumulative sum charts detect gradual shifts before they cross SPC thresholds, enabling proactive correction rather than reactive alarm response
- **R2R correction**: Each cycle's actual fill result feeds back into the next cycle's valve timing adjustment, creating a closed correction loop that self-tunes without operator input
- **Three-tier data architecture**: LOCAL (SQLite) → FIREBASE (Firestore) → SERVER (FastAPI + Neon PostgreSQL), switchable from the Android app, demonstrates progressive cloud migration with the same UI

---

## Key Results

| Component | Detail |
|-----------|--------|
| Error detection | SPC control charts + CUSUM drift monitoring |
| Correction loop | R2R (run-to-run) automatic valve timing adjustment |
| Prediction | LSTM fill time estimator (per SKU + history) |
| Real-time push | WebSocket `/ws/admin` → Android app + /admin page |
| Observability | Grafana panels: alarm frequency, error rate, model metrics |
| Data tiers | LOCAL (SQLite) / FIREBASE (Firestore) / SERVER (FastAPI + Neon) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python, MQTT (mosquitto) |
| Database | PostgreSQL (Neon) |
| ML Models | LSTM, SPC, CUSUM, R2R (PyTorch, scikit-learn) |
| Hardware | Arduino UNO (RFID, valve, LED, 7-segment) |
| Android App | Kotlin, Android Studio |
| Observability | WebSocket, Grafana, Docker |

---

## Project Structure

```
smartcan/
├── arduino/          # UNO sketch (RFID mapping, valve control, LED/LCD)
├── backend/          # FastAPI server (MQTT listener, ML inference, REST + WebSocket)
├── dashboard-app/    # Android app (LOCAL/FIREBASE/SERVER mode switching)
├── infra/            # Docker Compose (local dev: Postgres, MQTT, Grafana)
└── esp_bridge.py     # Serial ↔ MQTT bridge
```

---

## Getting Started

```bash
# 1. Local infrastructure (Postgres + MQTT + Grafana)
cd infra && docker compose up -d

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set: DATABASE_URL, MQTT_BROKER_HOST, MQTT_BROKER_PORT
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Serial bridge (when Arduino is connected)
python esp_bridge.py

# 4. Android app
# Open dashboard-app/ in Android Studio → Run
# Switch data source in dashboard-app/app/build.gradle.kts:
#   DATA_SOURCE = "LOCAL" | "FIREBASE" | "SERVER"
```

---

## Limitations & Future Work

- LSTM is trained on synthetic/lab data; retraining on production fill history would significantly improve timing prediction accuracy
- CUSUM threshold is currently manually tuned; adaptive threshold estimation based on process history would reduce configuration burden
- Future: multi-line support; predictive maintenance alerts based on valve wear patterns; OTA firmware updates for Arduino

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Author

**Seoyeon Kim** | Undergraduate Researcher  
[GitHub](https://github.com/gksmfly) · [Email](mailto:gimhaneul24@gmail.com)
