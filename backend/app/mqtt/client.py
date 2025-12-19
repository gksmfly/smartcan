# app/mqtt/client.py

from __future__ import annotations

import json
import threading
import time
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt

from app.core.config import settings
from app.db.session import SessionLocal
from app.ml.lstm_a import compute_next_valve_time
from app.services import line_state_service
from app.services.cycles_service import log_can_in_event, log_fill_result_event
from app.ws.bus import ws_bus

# 토픽 정의
TOPIC_CAN_IN = "line1/event/can_in"             # UNO → ESP → MQTT (RFID 태깅)
TOPIC_FILL_RESULT = "line1/event/fill_result"  # UNO → ESP → MQTT (충전 결과)
TOPIC_CMD_FILL = "line1/cmd/fill"              # 서버 → ESP → UNO (fill 명령)
TOPIC_CMD_CORR = "line1/cmd/corr"              # 서버 → ESP → UNO (보정 명령)


def infer_target_ml_from_sku(sku_id: str) -> float:
    """
    예) COKE_355 -> 355.0, CIDER_500 -> 500.0
    """
    try:
        tail = sku_id.split("_")[-1]
        return float(tail)
    except Exception:
        return 0.0


def set_current_sku_safe(db, sku_id: str, line_id: str = "line1") -> None:
    """
    line_state_service 시그니처가 (db, sku, line_id) / (db, sku) 둘 다 가능하게 방어.
    실패해도 전체 파이프라인은 계속 진행.
    """
    try:
        line_state_service.set_current_sku(db, sku=sku_id, line_id=line_id)
        db.commit()
    except TypeError:
        try:
            line_state_service.set_current_sku(db, sku=sku_id)
            db.commit()
        except Exception as e:
            db.rollback()
            print("[MQTT] set_current_sku failed:", repr(e))
    except Exception as e:
        db.rollback()
        print("[MQTT] set_current_sku failed:", repr(e))


class SmartCanMqttClient:
    def __init__(self) -> None:
        client_id = settings.MQTT_CLIENT_ID or "smartcan-backend"
        self.client = mqtt.Client(client_id=client_id, clean_session=True)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    # ========== 시작 ==========

    def start(self) -> None:
        host = settings.MQTT_BROKER_HOST
        port = settings.MQTT_BROKER_PORT

        print(f"[MQTT] Connecting to {host}:{port} (id={self.client._client_id})")
        self.client.connect(host, port, keepalive=60)

        t = threading.Thread(target=self.client.loop_forever, daemon=True)
        t.start()
        print("[MQTT] loop thread started")

    # ========== 콜백 ==========

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        print(f"[MQTT] Connected rc={reason_code}")
        client.subscribe(TOPIC_CAN_IN, qos=1)
        client.subscribe(TOPIC_FILL_RESULT, qos=1)
        print(f"[MQTT] Subscribed: {TOPIC_CAN_IN}, {TOPIC_FILL_RESULT}")

    def _on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode("utf-8")
            print(f"[MQTT] recv topic={msg.topic} payload={payload_str}")
            if not payload_str:
                return
            data = json.loads(payload_str)
        except Exception as e:
            print("[MQTT] payload decode error:", repr(e))
            return

        if msg.topic == TOPIC_CAN_IN:
            self._handle_can_in(data)
        elif msg.topic == TOPIC_FILL_RESULT:
            self._handle_fill_result(data)

    # ========== CAN_IN 핸들러 ==========

    def _handle_can_in(self, data: Dict[str, Any]) -> None:
        db = SessionLocal()
        try:
            raw_sku = data.get("sku") or data.get("sku_id")
            raw_seq = data.get("seq") or data.get("cycle_no")

            if not raw_sku or raw_seq is None:
                print(f"[MQTT] can_in missing sku/seq: {data}")
                return

            sku_id = str(raw_sku).strip()
            cycle_no = int(raw_seq)

            # target_ml 없으면 SKU에서 추론
            target_val = data.get("target_ml")
            if target_val is None:
                target_val = data.get("target_amount")

            try:
                target_amount = float(target_val) if target_val is not None else 0.0
            except Exception:
                target_amount = 0.0

            if target_amount <= 0.0:
                target_amount = infer_target_ml_from_sku(sku_id)

            # current_sku는 먼저 저장(실패해도 계속)
            try:
                line_state_service.set_current_sku(db, sku=sku_id, line_id="line1")
                db.commit()
            except Exception as e:
                db.rollback()
                print("[MQTT] set_current_sku failed:", repr(e))

            print(f"[MQTT] CAN_IN sku_id={sku_id} cycle_no={cycle_no} target={target_amount}")

            # ✅ 1) cycles를 먼저 “무조건” 적재 (valve_ms는 0으로)
            cycle = log_can_in_event(db, {
                "seq": cycle_no,
                "sku": sku_id,
                "target_ml": target_amount,
                "valve_ms": 0.0,
            })

            # ✅ 2) 그 다음 valve 계산 (실패해도 cycle은 이미 DB에 있음)
            valve_time = 0.0
            try:
                valve_time = float(compute_next_valve_time(db, sku_id=sku_id, target_amount=float(cycle.target_ml or target_amount)))
            except Exception as e:
                print("[MQTT] compute_next_valve_time failed:", repr(e))

            # ✅ 3) valve_ms 업데이트
            try:
                cycle.valve_ms = valve_time
                db.add(cycle)
                db.commit()
                db.refresh(cycle)
            except Exception as e:
                db.rollback()
                print("[MQTT] cycle valve_ms update failed:", repr(e))

            # ✅ 4) fill 명령은 valve_time 유효할 때만
            if valve_time > 0.0:
                self.publish_fill_command({
                    "sku": cycle.sku,
                    "seq": cycle.seq,
                    "target_ml": float(cycle.target_ml or 0.0),
                    "valve_ms": float(valve_time),
                    "mode": "SIM",
                })

            ws_bus.emit({
                "type": "can_in",
                "ts": int(time.time()),
                "data": {
                    "seq": cycle.seq,
                    "sku_id": cycle.sku,
                    "target_ml": float(cycle.target_ml or 0.0),
                    "valve_ms": float(valve_time),
                },
            })

        except Exception as e:
            db.rollback()
            print("[MQTT] handle_can_in error:", repr(e), "data=", data)
        finally:
            db.close()


    # ========== FILL_RESULT 핸들러 ==========

    def _handle_fill_result(self, data: Dict[str, Any]) -> None:
        """line1/event/fill_result"""
        db = SessionLocal()
        try:
            raw_seq = data.get("seq") if data.get("seq") is not None else data.get("cycle_no")
            raw_sku = data.get("sku") if data.get("sku") is not None else data.get("sku_id")

            cycle_no = int(raw_seq) if raw_seq is not None else 0
            sku_id = str(raw_sku or "UNKNOWN").strip()

            # actual_ml / valve_ms는 fill_result에서 필수로 들어오게 유지
            measured_val = data.get("actual_ml")
            if measured_val is None:
                measured_val = data.get("measured_value")
            measured_value = float(measured_val) if measured_val is not None else 0.0

            valve_val = data.get("valve_ms")
            if valve_val is None:
                valve_val = data.get("valve_time")
            valve_time = float(valve_val) if valve_val is not None else 0.0

            # ⚠️ target_ml은 “없으면 None”으로 두고, 0.0으로 덮어쓰지 않게
            tval = data.get("target_ml")
            if tval is None:
                tval = data.get("target_amount")
            target_ml: Optional[float]
            try:
                target_ml = float(tval) if tval is not None else None
                if target_ml is not None and target_ml <= 0.0:
                    target_ml = None
            except Exception:
                target_ml = None

            status = str(data.get("status", "DONE"))

            # (선택) fill_result로도 current_sku 갱신(안전망)
            if sku_id and sku_id != "UNKNOWN":
                set_current_sku_safe(db, sku_id=sku_id, line_id="line1")

            payload = {
                "seq": cycle_no,
                "sku": sku_id,
                "actual_ml": measured_value,
                "valve_ms": valve_time,
                "status": status,
            }
            if target_ml is not None:
                payload["target_ml"] = target_ml

            cycle = log_fill_result_event(db, payload)

            # Option C: WS push (fill_result)
            ws_bus.emit({
                "type": "fill_result",
                "ts": int(time.time()),
                "data": {
                    "seq": cycle.seq,
                    "sku_id": cycle.sku,
                    "target_ml": float(cycle.target_ml or target_ml or 0.0),
                    "actual_ml": float(cycle.actual_ml or measured_value),
                    "valve_ms": float(cycle.valve_ms or valve_time),
                    "status": status,
                },
            })

            db.commit()
        except Exception as e:
            db.rollback()
            print("[MQTT] handle_fill_result error:", repr(e), "data=", data)
        finally:
            db.close()

    # ========== publish 헬퍼 ==========

    def publish_fill_command(self, payload: Dict[str, Any]) -> None:
        data_str = json.dumps(payload, ensure_ascii=False)
        print(f"[MQTT] publish -> {TOPIC_CMD_FILL}: {data_str}")
        self.client.publish(TOPIC_CMD_FILL, data_str, qos=1, retain=False)

    def publish_corr_command(self, payload: Dict[str, Any]) -> None:
        data_str = json.dumps(payload, ensure_ascii=False)
        print(f"[MQTT] publish -> {TOPIC_CMD_CORR}: {data_str}")
        self.client.publish(TOPIC_CMD_CORR, data_str, qos=1, retain=False)


mqtt_client = SmartCanMqttClient()


def main():
    mqtt_client.start()
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
