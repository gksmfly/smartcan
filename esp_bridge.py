import os
import time
import json
import serial
import paho.mqtt.client as mqtt

# =========================
# 설정 (환경변수 우선)
# =========================
SERIAL_PORT = os.getenv("SERIAL_PORT", "COM5")   # Windows: COM5 / Linux: /dev/ttyUSB0 등
BAUD_RATE = int(os.getenv("BAUD_RATE", "9600"))

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")  # WSL mosquitto면 WSL IP 넣기
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

print("=== pc-bridge starting ===")
print(f"[CFG] SERIAL_PORT={SERIAL_PORT}, BAUD_RATE={BAUD_RATE}")
print(f"[CFG] MQTT={MQTT_HOST}:{MQTT_PORT}")

# =========================
# 시리얼 포트 오픈
# =========================
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    time.sleep(2.0)  # 아두이노 리셋 안정화
    try:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
    except Exception:
        pass
    print("[SERIAL] port opened")
except Exception as e:
    print("[SERIAL] ERROR: cannot open serial port:", repr(e))
    raise

# =========================
# MQTT 클라이언트
# =========================
client = mqtt.Client(client_id="pc-bridge")

def on_connect(c, userdata, flags, rc, properties=None):
    print("[MQTT] connected rc=", rc)
    c.subscribe("line1/cmd/fill", qos=1)
    c.subscribe("line1/cmd/corr", qos=1)
    print("[MQTT] subscribed: line1/cmd/fill, line1/cmd/corr")

def on_message(c, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="ignore")
    print(f"[MQTT] recv {msg.topic}: {payload}")

    if msg.topic == "line1/cmd/fill":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            print("[WARN] invalid JSON payload for fill cmd")
            return

        seq = int(data.get("seq", 0))
        target_ml = float(data.get("target_ml") or data.get("target_amount") or 0.0)
        mode = data.get("mode", "SIM")
        valve_ms = int(float(data.get("valve_ms") or data.get("valve_time") or 0))

        line = f"F,{seq},{target_ml},{mode},{valve_ms}\n"
        try:
            ser.write(line.encode("utf-8"))
            print("[SERIAL<-MQTT]", line.strip())
        except Exception as e:
            print("[SERIAL] write error:", repr(e))

    elif msg.topic == "line1/cmd/corr":
        try:
            ser.write(b"CORR\n")
            print("[SERIAL<-MQTT] CORR")
        except Exception as e:
            print("[SERIAL] write error (CORR):", repr(e))

client.on_connect = on_connect
client.on_message = on_message

print("[MQTT] connecting...")
client.connect(MQTT_HOST, MQTT_PORT, 60)
client.loop_start()
print("[MQTT] loop started")
print("=== Serial <-> MQTT bridge started ===")

# =========================
# 메인 루프: UNO → MQTT
# =========================
try:
    while True:
        raw = ser.readline()
        if not raw:
            time.sleep(0.01)
            continue

        line = raw.decode("utf-8", errors="ignore").strip()
        if not line:
            continue

        print("[SERIAL]", line)

        # UNO 포맷: P:topic:payload
        if line.startswith("P:"):
            try:
                _, topic, payload = line.split(":", 2)
            except ValueError:
                print("[WARN] invalid P: line")
                continue

            print(f"[MQTT] publish {topic} {payload}")
            client.publish(topic, payload, qos=1)

except KeyboardInterrupt:
    print("\n[MAIN] KeyboardInterrupt, exiting...")

finally:
    print("[MAIN] cleaning up...")
    try: client.loop_stop()
    except Exception: pass
    try: client.disconnect()
    except Exception: pass
    try: ser.close()
    except Exception: pass
