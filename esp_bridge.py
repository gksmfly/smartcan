import time
import json
import serial
import paho.mqtt.client as mqtt

# =========================
# 설정
# =========================
# 👉 Mac 예: "/dev/cu.usbmodem141011"
# 👉 Windows 예: "COM5"
SERIAL_PORT = "/dev/cu.usbmodem141011"
BAUD_RATE = 9600

MQTT_HOST = "localhost"
MQTT_PORT = 1883

print("=== pc-bridge starting ===")
print(f"[CFG] SERIAL_PORT={SERIAL_PORT}, BAUD_RATE={BAUD_RATE}")
print(f"[CFG] MQTT={MQTT_HOST}:{MQTT_PORT}")

# =========================
# Serial 연결
# =========================
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    print("[SERIAL] port opened")
except Exception as e:
    print("[SERIAL] ERROR: cannot open serial port:", e)
    raise


# =========================
# MQTT 클라이언트
# =========================
client = mqtt.Client(client_id="pc-bridge")


def on_connect(c, userdata, flags, rc, properties=None):
    print("[MQTT] connected rc=", rc)
    c.subscribe("line1/cmd/fill", qos=1)


def on_message(c, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="ignore")
    print(f"[MQTT] recv {msg.topic}: {payload}")

    # ======================================================
    #   서버 → ESP → UNO : fill 명령 처리
    # ======================================================
    if msg.topic == "line1/cmd/fill":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            print("[WARN] invalid JSON payload")
            return

        seq = int(data.get("seq", 0))
        target_ml = float(data.get("target_ml") or data.get("target_amount") or 0.0)
        valve_ms = float(data.get("valve_ms") or data.get("valve_time") or 0.0)
        mode = str(data.get("mode", "SIM"))

        valve_ms_int = int(valve_ms)

        # UNO 명령 포맷
        cmd = f"F,{seq},{target_ml},{mode},{valve_ms_int}\n"

        try:
            ser.write(cmd.encode("utf-8"))
            print("[SERIAL<-MQTT]", cmd.strip())
        except Exception as e:
            print("[SERIAL] write error:", e)


client.on_connect = on_connect
client.on_message = on_message


print("[MQTT] connecting...")
client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
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

        try:
            line = raw.decode("utf-8", errors="ignore").strip()
        except Exception:
            continue

        if not line:
            continue

        print("[SERIAL]", line)

        # UNO → MQTT : "P:topic:payload"
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
    try:
        client.loop_stop()
    except Exception:
        pass

    try:
        client.disconnect()
    except Exception:
        pass

    try:
        ser.close()
    except Exception:
        pass