import cv2
import numpy as np
import json

VIDEO_SOURCE = "Video\\test_video1.mp4" # webcam
POINT_RADIUS = 8
area_points = []
dragging_idx = None

def click_event(event, x, y, flags, param):
    global dragging_idx

    if event == cv2.EVENT_LBUTTONDOWN:
        for i, (px, py) in enumerate(area_points):
            if abs(x - px) < POINT_RADIUS and abs(y - py) < POINT_RADIUS:
                dragging_idx = i
                return
        area_points.append((x, y))

    elif event == cv2.EVENT_MOUSEMOVE and dragging_idx is not None:
        area_points[dragging_idx] = (x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        dragging_idx = None

# Ambil frame awal dari kamera
cap = cv2.VideoCapture(VIDEO_SOURCE)
DISPLAY_WIDTH, DISPLAY_HEIGHT = 1280, 720
ret, frame = cap.read()
cap.release()

if not ret:
    print("Gagal membaca frame kamera.")
    exit()

clone = frame.copy()
cv2.namedWindow("Setup Area", cv2.WINDOW_NORMAL)
cv2.setMouseCallback("Setup Area", click_event)
resized_frame = cv2.resize(clone, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
while True:
    temp = resized_frame.copy()

    if len(area_points) > 1:
        cv2.polylines(temp, [np.array(area_points)], isClosed=True, color=(0, 255, 255), thickness=2)

    for (x, y) in area_points:
        cv2.circle(temp, (x, y), POINT_RADIUS, (0, 0, 255), -1)

    cv2.putText(temp, "Tekan S untuk Simpan, Q untuk Keluar", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    cv2.imshow("Setup Area", temp)
    key = cv2.waitKey(1)
    if key == ord('s'):
        if len(area_points) >= 3:
            with open("config.json", "w") as f:
                json.dump({"area": area_points}, f)
            print("Area berhasil disimpan ke config.json")
        else:
            print("Minimal 3 titik untuk area!")
    elif key == ord('q'):
        break

cv2.destroyAllWindows()
