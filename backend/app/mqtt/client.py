# app/mqtt/client.py

import json
import threading
from typing import Any, Dict

import paho.mqtt.client as mqtt

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.cycles_service import (
    log_can_in_event,
    log_fill_result_event,
    get_recent_cycles_for_sku,
)
from app.services.recipes_service import get_recipe_by_sku_id
from app.services.r2r import compute_next_valve_time
from app.ml.lstm_a import get_lstm_a_model

TOPIC_CAN_IN = "line1/event/can_in"
TOPIC_FILL_RESULT = "line1/event/fill_result"
TOPIC_CMD_FILL = "line1/cmd/fill"


class SmartCanMqttClient:
    def __init__(self):
        client_id = settings.MQTT_CLIENT_ID or "smartcan-backend"
        self.client = mqtt.Client(client_id=client_id, clean_session=True)

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    # -------------------------------------------------------------
    # MQTT START
    # -------------------------------------------------------------
    def start(self):
        host = settings.MQTT_BROKER_HOST
        port = settings.MQTT_BROKER_PORT

        print(f"[MQTT] Connecting to {host}:{port}")
        self.client.connect(host, port, keepalive=60)

        t = threading.Thread(target=self.client.loop_forever, daemon=True)
        t.start()
        print("[MQTT] loop started")

    # -------------------------------------------------------------
    # CALLBACK
    # -------------------------------------------------------------
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"[MQTT] Connected rc={rc}")
        client.subscribe(TOPIC_CAN_IN, qos=1)
        client.subscribe(TOPIC_FILL_RESULT, qos=1)
        print(f"[MQTT] Subscribed {TOPIC_CAN_IN}, {TOPIC_FILL_RESULT}")

    def _on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode()
            print(f"[MQTT] recv topic={msg.topic} payload={payload_str}")
            data = json.loads(payload_str)
        except Exception as e:
            print("[MQTT] decode error:", e)
            return

        if msg.topic == TOPIC_CAN_IN:
            self._handle_can_in(data)
        elif msg.topic == TOPIC_FILL_RESULT:
            self._handle_fill_result(data)

    # -------------------------------------------------------------
    # CAN_IN 핸들러
    # -------------------------------------------------------------
    def _handle_can_in(self, data: Dict[str, Any]):
        """
        { "seq":1, "uid":"XXXX", "sku":"COKE_355", "target_ml":355.0 }
        """
        db = SessionLocal()
        try:
            sku_id = str(data.get("sku"))
            cycle_no = int(data.get("seq"))
            target_ml = float(data.get("target_ml"))

            print(f"[MQTT] CAN_IN sku={sku_id}, seq={cycle_no}, target={target_ml}")

            # 1) 레시피 로드
            recipe = get_recipe_by_sku_id(db, sku_id)
            if not recipe:
                raise Exception(f"Recipe not found for sku={sku_id}")

            # 2) 최근 cycle 50개 로드
            recent = get_recent_cycles_for_sku(db, sku=sku_id, limit=50)

            # 3) LSTM-A 모델 로드
            lstm_a = get_lstm_a_model()
            predicted_next_amount = lstm_a.predict_next_amount(recipe, recent)

            # 4) R2R로 next valve 시간 계산
            next_valve_ms = compute_next_valve_time(
                recipe=recipe,
                recent_cycles=recent,
                predicted_next_amount=predicted_next_amount,
            )

            # 5) DB에 can_in 이벤트 기록
            cycle_payload = {
                "seq": cycle_no,
                "sku": sku_id,
                "target_ml": target_ml,
                "valve_ms": next_valve_ms,
            }
            cycle = log_can_in_event(db, cycle_payload)

            # 6) UNO로 fill 명령 전송
            cmd = {
                "sku": cycle.sku,
                "seq": cycle.seq,
                "target_ml": cycle.target_ml,
                "valve_ms": next_valve_ms,
                "mode": "SIM",
            }
            self.publish_fill_command(cmd)

            db.commit()

        except Exception as e:
            db.rollback()
            print("[MQTT] handle_can_in error:", e)
        finally:
            db.close()

    # -------------------------------------------------------------
    # FILL_RESULT 핸들러
    # -------------------------------------------------------------
    def _handle_fill_result(self, data: Dict[str, Any]):
        """
        {
          "seq":1, "sku":"COKE_355",
          "actual_ml":350.5, "target_ml":355.0,
          "valve_ms":300, "status":"OK"
        }
        """
        db = SessionLocal()
        try:
            payload = {
                "seq": int(data.get("seq")),
                "sku": data.get("sku"),
                "actual_ml": float(data.get("actual_ml")),
                "target_ml": float(data.get("target_ml")),
                "valve_ms": float(data.get("valve_ms")),
                "status": data.get("status", "DONE"),
            }
            log_fill_result_event(db, payload)
            db.commit()

        except Exception as e:
            db.rollback()
            print("[MQTT] handle_fill_result error:", e)
        finally:
            db.close()

    # -------------------------------------------------------------
    # publish helper
    # -------------------------------------------------------------
    def publish_fill_command(self, payload: Dict[str, Any]):
        data_str = json.dumps(payload, ensure_ascii=False)
        print(f"[MQTT] publish -> {TOPIC_CMD_FILL}: {data_str}")
        self.client.publish(TOPIC_CMD_FILL, data_str, qos=1)


mqtt_client = SmartCanMqttClient()