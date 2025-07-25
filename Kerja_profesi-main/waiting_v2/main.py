from flask import Flask, render_template, Response
import cv2
import json
import time
import numpy as np
from shapely.geometry import Point, Polygon
from ultralytics import YOLO
import paho.mqtt.client as mqtt

# === Flask App ===
app = Flask(__name__)

# === MQTT Konfigurasi ===
MQTT_BROKER = "broker.mqtt-dashboard.com"
MQTT_PORT = 1883
MQTT_TOPIC = "pedestrian/status"
client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT)
last_published_time = time.time()
mqtt_CD = 2

# === Waktu Konfigurasi ===
MIN_WAIT_TIME = 5
DELAY_GREEN_OFF = 3

# === Load Konfigurasi Area ===
with open("config.json", "r") as f:
    config = json.load(f)
area_wait = config["area_wait"]
area_cross = config["area_cross"]
polygon_wait = Polygon(area_wait)
polygon_cross = Polygon(area_cross)

# === Load Model dan Video ===
model = YOLO("yolo11n.pt")
cap = cv2.VideoCapture("test_video4.mp4")
DISPLAY_WIDTH, DISPLAY_HEIGHT = 640, 640

# === Variabel Status ===
waiting_ids = {}
green_light_start = None
no_detection_timer = None
lampu_hijau_pejalan = False
status = 0


def generate_frames():
    global last_published_time, waiting_ids, green_light_start, no_detection_timer, lampu_hijau_pejalan, status

    while True:
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        frame = cv2.resize(frame, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        start_frame_time = time.time()

        # Masking area
        mask = np.zeros_like(frame[:, :, 0])
        cv2.fillPoly(mask, [np.array(area_wait, np.int32)], 255)
        cv2.fillPoly(mask, [np.array(area_cross, np.int32)], 255)
        masked_frame = cv2.bitwise_and(frame, frame, mask=mask)

        results = model.predict(masked_frame, conf=0.25, classes=[0])
        annotated = frame.copy()
        current_time = time.time()
        ada_di_waiting_area = False
        ada_di_crossing_area = False

        for result in results:
            boxes = result.boxes.xyxy.cpu().numpy() if result.boxes else []
            ids = np.arange(len(boxes))

            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box)
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                center = Point((cx, cy))
                id = ids[i]

                if polygon_wait.contains(center):
                    ada_di_waiting_area = True
                    if id not in waiting_ids:
                        waiting_ids[id] = current_time

                    elapsed = current_time - waiting_ids[id]
                    cv2.putText(annotated, f"{int(elapsed)}s", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

                    if elapsed >= MIN_WAIT_TIME:
                        lampu_hijau_pejalan = True
                        green_light_start = current_time
                        no_detection_timer = None

                elif polygon_cross.contains(center):
                    ada_di_crossing_area = True
                    no_detection_timer = None
                else:
                    waiting_ids.pop(id, None)

                # Draw boxes
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(annotated, (cx, cy), 4, (0, 0, 255), -1)

        # Logika lampu
        if lampu_hijau_pejalan:
            status = 1
            if not ada_di_crossing_area:
                if no_detection_timer is None:
                    no_detection_timer = current_time
                elif current_time - no_detection_timer > DELAY_GREEN_OFF:
                    lampu_hijau_pejalan = False
                    waiting_ids.clear()
                    no_detection_timer = None
        else:
            status = 0
            no_detection_timer = None

        # Gambar area
        cv2.polylines(annotated, [np.array(area_wait)], True, (0, 255, 255), 2)
        cv2.polylines(annotated, [np.array(area_cross)], True, (255, 255, 0), 2)

        # Gambar status lampu
        if lampu_hijau_pejalan:
            cv2.rectangle(annotated, (20, 20), (160, 70), (0, 255, 0), -1)
            cv2.putText(annotated, "WALK", (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        else:
            cv2.rectangle(annotated, (20, 20), (160, 70), (0, 0, 255), -1)
            cv2.putText(annotated, "STOP", (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        # MQTT
        if (current_time - last_published_time) >= mqtt_CD:
            client.publish(MQTT_TOPIC, status)
            print(f"[MQTT] Published: {status}")
            last_published_time = current_time

        # FPS
        fps = 1 / (time.time() - start_frame_time + 1e-6)
        cv2.putText(annotated, f"FPS: {fps:.2f}", (20, DISPLAY_HEIGHT - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Encode ke JPEG
        ret, buffer = cv2.imencode('.jpg', annotated)
        frame_bytes = buffer.tobytes()

        # Yield untuk web
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video')
def video():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == '__main__':
    app.run(debug=True)
