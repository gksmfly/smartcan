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
TOPIC_CAN_IN = "line1/event/can_in"            # UNO → ESP → MQTT (RFID 태깅)
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


class SmartCanMqttClient:
    def __init__(self) -> None:
        client_id = settings.MQTT_CLIENT_ID or "smartcan-backend"
        self.client = mqtt.Client(client_id=client_id, clean_session=True)

        # 필요시 계정
        # if settings.MQTT_USERNAME:
        #     self.client.username_pw_set(
        #         settings.MQTT_USERNAME,
        #         settings.MQTT_PASSWORD,
        #     )

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
            print("[MQTT] payload decode error:", e)
            return

        if msg.topic == TOPIC_CAN_IN:
            self._handle_can_in(data)
        elif msg.topic == TOPIC_FILL_RESULT:
            self._handle_fill_result(data)

    # ========== CAN_IN 핸들러 ==========

    def _handle_can_in(self, data: Dict[str, Any]) -> None:
        """line1/event/can_in"""
        db = SessionLocal()
        try:
            raw_sku = data.get("sku") or data.get("sku_id")
            raw_seq = data.get("seq") or data.get("cycle_no")

            if not raw_sku or raw_seq is None:
                print(f"[MQTT] can_in missing sku/seq: {data}")
                return

            sku_id = str(raw_sku).strip()
            if not sku_id:
                print(f"[MQTT] can_in empty sku: {data}")
                return

            try:
                cycle_no = int(raw_seq)
            except Exception:
                print(f"[MQTT] can_in invalid seq: {data}")
                return

            # target_ml 없거나 0이면 SKU에서 추론
            target_val = data.get("target_ml")
            if target_val is None:
                target_val = data.get("target_amount")

            try:
                target_amount = float(target_val) if target_val is not None else 0.0
            except Exception:
                target_amount = 0.0

            if target_amount <= 0.0:
                inferred = infer_target_ml_from_sku(sku_id)
                if inferred > 0.0:
                    target_amount = inferred

            # ✅ current_sku는 can_in 성공/실패와 무관하게 먼저 저장(튐 방지)
            try:
                line_state_service.set_current_sku(db, sku=sku_id, line_id="line1")
                # set_current_sku 내부에서 commit을 하든 안 하든, 여기서 한 번 더 커밋해도 안전
                db.commit()
            except Exception as e:
                # current_sku 저장 실패해도 can_in 자체를 계속 진행할 수 있게
                db.rollback()
                print("[MQTT] set_current_sku failed:", repr(e))

            # target_amount가 끝까지 0이면, log_can_in_event가 죽을 가능성이 높으니 여기서 중단
            if target_amount <= 0.0:
                print(f"[MQTT] CAN_IN target missing/invalid; skip cycle write. sku={sku_id} data={data}")
                return

            print(f"[MQTT] CAN_IN sku_id={sku_id} cycle_no={cycle_no} target={target_amount}")

            # 1) LSTM-A(+R2R)로 밸브 시간 계산
            valve_time = compute_next_valve_time(db, sku_id=sku_id, target_amount=target_amount)

            # 2) DB 기록
            cycle = log_can_in_event(db, {
                "seq": cycle_no,
                "sku": sku_id,
                "target_ml": target_amount,
                "valve_ms": valve_time,
            })

            # 3) 장비로 fill 명령
            cmd_payload = {
                "sku": cycle.sku,
                "seq": cycle.seq,
                "target_ml": cycle.target_ml,
                "valve_ms": valve_time,
                "mode": "SIM",
            }
            self.publish_fill_command(cmd_payload)

            # 4) Option C: 관리자 WS로 이벤트 push
            ws_bus.emit({
                "type": "can_in",
                "ts": int(time.time()),
                "data": {
                    "seq": cycle.seq,
                    "sku_id": cycle.sku,
                    "target_ml": float(cycle.target_ml),
                    "valve_ms": float(valve_time),
                },
            })

            db.commit()

        except Exception as e:
            db.rollback()
            print("[MQTT] handle_can_in error:", e)
        finally:
            db.close()

    # ========== FILL_RESULT 핸들러 ==========

    def _handle_fill_result(self, data: Dict[str, Any]) -> None:
        """line1/event/fill_result"""
        db = SessionLocal()
        try:
            cycle_no = int(data.get("seq") or data.get("cycle_no") or 0)
            sku_id = str(data.get("sku") or data.get("sku_id") or "UNKNOWN").strip()

            measured_value = float(data.get("actual_ml") or data.get("measured_value") or 0.0)
            target_ml = float(data.get("target_ml") or data.get("target_amount") or 0.0)
            valve_time = float(data.get("valve_ms") or data.get("valve_time") or 0.0)
            status = str(data.get("status", "DONE"))

            # (선택) fill_result로도 current_sku 갱신(안전망)
            if sku_id and sku_id != "UNKNOWN":
                try:
                    line_state_service.set_current_sku(db, sku=sku_id, line_id="line1")
                    db.commit()
                except Exception as e:
                    db.rollback()
                    print("[MQTT] set_current_sku (fill_result) failed:", repr(e))

            cycle = log_fill_result_event(db, {
                "seq": cycle_no,
                "sku": sku_id,
                "actual_ml": measured_value,
                "target_ml": target_ml,
                "valve_ms": valve_time,
                "status": status,
            })

            # Option C: WS push (fill_result)
            ws_bus.emit({
                "type": "fill_result",
                "ts": int(time.time()),
                "data": {
                    "seq": cycle.seq,
                    "sku_id": cycle.sku,
                    "target_ml": float(cycle.target_ml or target_ml),
                    "actual_ml": float(cycle.actual_ml or measured_value),
                    "valve_ms": float(cycle.valve_ms or valve_time),
                    "status": status,
                },
            })

            db.commit()
        except Exception as e:
            db.rollback()
            print("[MQTT] handle_fill_result error:", e)
        finally:
            db.close()

    # ========== publish 헬퍼 ==========

    def publish_fill_command(self, payload: Dict[str, Any]) -> None:
        data_str = json.dumps(payload, ensure_ascii=False)
        print(f"[MQTT] publish -> {TOPIC_CMD_FILL}: {data_str}")
        self.client.publish(TOPIC_CMD_FILL, data_str, qos=1, retain=False)

    def publish_corr_command(self, payload: Dict[str, Any]) -> None:
        """서버 → ESP/브리지 → UNO 방향 보정(CORR) 명령"""
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
