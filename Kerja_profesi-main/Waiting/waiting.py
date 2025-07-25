import cv2
import json
import time
import numpy as np
from shapely.geometry import Point, Polygon
from ultralytics import YOLO
import paho.mqtt.client as mqtt 
# load mqtt server configuration
MQTT_BROKER = "broker.mqtt-dashboard.com" # Ganti dengan IP broker kamu
MQTT_PORT = 1883
MQTT_TOPIC = "pedestrian/status"

client = mqtt.Client()
client.connect(MQTT_BROKER, MQTT_PORT)
last_published_time = time.time()
mqtt_CD = 2  # Cooldown untuk publish status
# === 1. Load Area dari config.json ===
with open("config.json", "r") as f:
    config = json.load(f)

area_points = config["area"]
polygon_area = Polygon(area_points)

# === 2. Inisialisasi Model dan Kamera ===
# model = YOLO("yolov8n.pt") # pastikan file .pt ada
# # menggunakan tensor rt pada model
# model.export(format="engine")

e_model = YOLO("yolov8n.engine") # pastikan file .engine ada
cap = cv2.VideoCapture("Video\\test_video1.avi")  # 0 untuk webcam
ret, frame = cap.read()

if not ret:
    print("Gagal membuka video.")
    exit()

# Target ukuran tampilan
DISPLAY_WIDTH, DISPLAY_HEIGHT = 640, 640


# === 3. Konfigurasi lainnya ===
MIN_WAIT_TIME = 5  # detik
id_timers = {}     # id: waktu_masuk_area
global last_status
last_status = None  # status terakhir yang dipublikasikan
global lampu_hijau_pejalan
lampu_hijau_pejalan = False  # status lampu pejalan kaki
global status
status = 0
# === 4. Loop Video ===
while True:
    ret, frame = cap.read()
    if not ret:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Kembali ke frame awal
        continue
        # break
    frame_start = time.time()
    # Resize frame ke 1280x720
    resized_frame = cv2.resize(frame, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
    model_frame = resized_frame.copy()
    # 5. Deteksi manusia
    results = e_model.track(model_frame, persist=True, conf=0.5, classes=[0], stream=True)  # class 0 = person
    annotated = resized_frame.copy()
    current_time = time.time()
    lampu_hijau_pejalan = False

    for result in results:
        if result.boxes.id is None:
            continue

        ids = result.boxes.id.cpu().numpy().astype(int)
        boxes = result.boxes.xyxy.cpu().numpy()

        for i, box in enumerate(boxes):
            id = ids[i]
            x1, y1, x2, y2 = map(int, box)
            center = ((x1 + x2) // 2, (y1 + y2) // 2)

            # 6. Cek apakah dalam area
            inside = polygon_area.contains(Point(center))
            if inside:
                if id not in id_timers:
                    id_timers[id] = current_time

                elapsed = current_time - id_timers[id]
                if elapsed >= MIN_WAIT_TIME:
                    lampu_hijau_pejalan = True

                cv2.putText(annotated, f"{int(elapsed)}s", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            else:
                id_timers.pop(id, None)

            # 7. Gambar kotak deteksi
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.circle(annotated, center, 4, (255, 0, 255), -1)
            cv2.putText(annotated, f"ID {id}", (x1, y2 + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        if lampu_hijau_pejalan:
            status = 1
        else:
            status = 0
        if (current_time - last_published_time) >= mqtt_CD:
            client.publish(MQTT_TOPIC, status)
            print(f"[MQTT] Published: {status}")
            last_status = status
            last_published_time = current_time
            # cv2.waitKey(0)  # Delay untuk menghindari spam publish
    # 8. Gambar area
    cv2.polylines(annotated, [np.array(area_points)], isClosed=True, color=(0, 255, 255), thickness=2)

    # 9. Gambar Lampu
    if lampu_hijau_pejalan and (current_time - last_published_time) >= mqtt_CD:
        # Merah kendaraan, Hijau pejalan
        cv2.rectangle(annotated, (20, 20), (160, 70), (0, 255, 0), -1)
        cv2.putText(annotated, "WALK", (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    elif not lampu_hijau_pejalan and (current_time - last_published_time) >= mqtt_CD:
        # Hijau kendaraan, Merah pejalan
        cv2.rectangle(annotated, (20, 20), (160, 70), (0, 0, 255), -1)
        cv2.putText(annotated, "STOP", (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    # 10. Tampilkan hasil
    cv2.imshow("Smart Pedestrian System", annotated)
    if cv2.waitKey(15) == ord('q'):
        break
    fps = 1 / (time.time() - frame_start)
    print(f"Frame FPS: {fps:.2f}")


cap.release()
cv2.destroyAllWindows()
