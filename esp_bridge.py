import time
import json
import serial
import paho.mqtt.client as mqtt

# =========================
# 설정
# =========================
# 👉 Windows: "COM5", "COM3" 처럼 사용
# 👉 Mac    : "/dev/cu.usbmodem141011" 이런 식으로 사용
SERIAL_PORT = "COM5"
BAUD_RATE = 9600

MQTT_HOST = "localhost"
MQTT_PORT = 1883

print("=== pc-bridge starting ===")
print(f"[CFG] SERIAL_PORT={SERIAL_PORT}, BAUD_RATE={BAUD_RATE}")
print(f"[CFG] MQTT={MQTT_HOST}:{MQTT_PORT}")

# =========================
# 시리얼 포트 오픈
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
    # 서버 → 하드웨어 방향: fill, corr 명령 구독
    c.subscribe("line1/cmd/fill", qos=1)
    c.subscribe("line1/cmd/corr", qos=1)


def on_message(c, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="ignore")
    print(f"[MQTT] recv {msg.topic}: {payload}")

    # 서버에서 내려온 fill JSON → UNO가 이해하는 "F,..." 형식으로 변환
    if msg.topic == "line1/cmd/fill":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            print("[WARN] invalid JSON payload for fill cmd")
            return

        # JSON에서 값 꺼내기 (키 이름 여러 케이스 방어)
        seq = int(data.get("seq", 0))

        target_ml = float(
            data.get("target_ml")
            or data.get("target_amount")
            or 0.0
        )

        mode = data.get("mode", "SIM")

        valve_ms = int(
            float(
                data.get("valve_ms")
                or data.get("valve_time")
                or 0
            )
        )

        # UNO가 기대하는 포맷: F,seq,target_ml,mode,valve_ms
        line = f"F,{seq},{target_ml},{mode},{valve_ms}\n"
        try:
            ser.write(line.encode("utf-8"))
            print("[SERIAL<-MQTT]", line.strip())
        except Exception as e:
            print("[SERIAL] write error:", e)

    # 보정 명령: UNO로 "CORR\n"만 내려주면 됨
    elif msg.topic == "line1/cmd/corr":
        try:
            ser.write(b"CORR\n")
            print("[SERIAL<-MQTT] CORR")
        except Exception as e:
            print("[SERIAL] write error (CORR):", e)


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

        # UNO가 sendMqttPublish로 보낸 라인: P:topic:payload 형태
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