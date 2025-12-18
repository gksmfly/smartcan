import json
import paho.mqtt.client as mqtt

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.cycles_service import log_can_in_event, log_fill_result_event

TOPICS = [
    ("line1/event/can_in", 0),
    ("line1/event/fill_result", 0),
]

def on_connect(client, userdata, flags, rc):
    print("[worker] connected rc=", rc)
    for t, qos in TOPICS:
        client.subscribe(t, qos=qos)
        print("[worker] subscribed:", t)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except Exception as e:
        print("[worker] bad json:", e, msg.payload)
        return

    db = SessionLocal()
    try:
        if msg.topic.endswith("can_in"):
            cycle = log_can_in_event(db, payload)
            print("[worker] can_in saved cycle_id=", getattr(cycle, "id", None))
        elif msg.topic.endswith("fill_result"):
            cycle = log_fill_result_event(db, payload)
            print("[worker] fill_result saved cycle_id=", getattr(cycle, "id", None))
        else:
            print("[worker] unknown topic:", msg.topic)
    except Exception as e:
        print("[worker] handler error:", repr(e), "topic=", msg.topic, "payload=", payload)
    finally:
        db.close()

client = mqtt.Client(client_id="smartcan-mqtt-worker")
client.on_connect = on_connect
client.on_message = on_message

client.connect(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, 60)
client.loop_forever()
