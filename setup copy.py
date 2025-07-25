import cv2
import numpy as np
import json

VIDEO_SOURCE = "test_video4.mp4"
DISPLAY_WIDTH, DISPLAY_HEIGHT = 640, 640
POINT_RADIUS = 8

area_wait = []
area_cross = []
dragging_idx = None
active_area = "wait"  # atau "cross"

def click_event(event, x, y, flags, param):
    global dragging_idx, active_area

    current_area = area_wait if active_area == "wait" else area_cross

    if event == cv2.EVENT_LBUTTONDOWN:
        for i, (px, py) in enumerate(current_area):
            if abs(x - px) < POINT_RADIUS and abs(y - py) < POINT_RADIUS:
                dragging_idx = i
                return
        current_area.append((x, y))

    elif event == cv2.EVENT_MOUSEMOVE and dragging_idx is not None:
        current_area[dragging_idx] = (x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        dragging_idx = None

# Ambil frame awal dari video
cap = cv2.VideoCapture(VIDEO_SOURCE)
ret, frame = cap.read()
cap.release()

if not ret:
    print("Gagal membaca frame video.")
    exit()

# Resize & rotasi
frame = cv2.resize(frame, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)

cv2.namedWindow("Setup Area", cv2.WINDOW_NORMAL)
cv2.setMouseCallback("Setup Area", click_event)

print("🟢 Klik untuk membuat area.")
print("Tekan [TAB] untuk ganti area: area_wait <-> area_cross")
print("Tekan [S] untuk simpan ke config.json")
print("Tekan [Q] untuk keluar")

while True:
    temp = frame.copy()

    # Gambar area_wait
    if len(area_wait) > 1:
        cv2.polylines(temp, [np.array(area_wait)], isClosed=True, color=(0, 255, 255), thickness=2)
    for (x, y) in area_wait:
        cv2.circle(temp, (x, y), POINT_RADIUS, (0, 255, 255), -1)

    # Gambar area_cross
    if len(area_cross) > 1:
        cv2.polylines(temp, [np.array(area_cross)], isClosed=True, color=(255, 255, 0), thickness=2)
    for (x, y) in area_cross:
        cv2.circle(temp, (x, y), POINT_RADIUS, (255, 255, 0), -1)

    # Tampilkan teks instruksi
    cv2.putText(temp, f"Area aktif: {'WAITING' if active_area=='wait' else 'CROSSING'}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(temp, "TAB: Ganti Area | S: Simpan | Q: Keluar", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    cv2.imshow("Setup Area", temp)
    key = cv2.waitKey(1)

    if key == 9:  # TAB key
        active_area = "cross" if active_area == "wait" else "wait"
    elif key == ord('s'):
        if len(area_wait) >= 3 and len(area_cross) >= 3:
            with open("config.json", "w") as f:
                json.dump({
                    "area_wait": area_wait,
                    "area_cross": area_cross
                }, f)
            print("✅ Area berhasil disimpan ke config.json")
        else:
            print("❌ Masing-masing area harus minimal 3 titik!")
    elif key == ord('q'):
        break

cv2.destroyAllWindows()
