import cv2
import numpy as np
import json

VIDEO_SOURCE = "Video/test_video4.mp4"
DISPLAY_WIDTH, DISPLAY_HEIGHT = 1280, 640
POINT_RADIUS = 8

area_wait = []
area_cross = []
area_middle = []
line = []
dragging_idx = None
active_area = "wait"  # "wait", "cross", "middle", "line"

def resize_with_aspect_ratio(image, width=None, height=None, inter=cv2.INTER_AREA):
    (h, w) = image.shape[:2]
    if width is None and height is None:
        return image
    if width is not None:
        r = width / float(w)
        dim = (width, int(h * r))
    else:
        r = height / float(h)
        dim = (int(w * r), height)
    return cv2.resize(image, dim, interpolation=inter)

def click_event(event, x, y, flags, param):
    global dragging_idx, active_area
    current_area = {
        "wait": area_wait,
        "cross": area_cross,
        "middle": area_middle,
        "line": line
    }[active_area]

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

frame = resize_with_aspect_ratio(frame, width=DISPLAY_WIDTH)
cv2.namedWindow("Setup Area", cv2.WINDOW_NORMAL)
cv2.setMouseCallback("Setup Area", click_event)

print("🟢 Klik untuk membuat area.")
print("Tekan [TAB] untuk ganti area: wait → cross → middle → line")
print("Tekan [S] untuk simpan ke config.json")
print("Tekan [Q] untuk keluar")

while True:
    temp = frame.copy()

    # Gambar semua area
    def draw_area(area, color):
        if len(area) > 1:
            cv2.polylines(temp, [np.array(area)], isClosed=True, color=color, thickness=2)
        for (x, y) in area:
            cv2.circle(temp, (x, y), POINT_RADIUS, color, -1)

    draw_area(area_wait, (0, 255, 255))
    draw_area(area_cross, (255, 255, 0))
    draw_area(area_middle, (255, 0, 255))

    # Gambar line jika sudah 2 titik
    if len(line) == 2:
        cv2.line(temp, line[0], line[1], (0, 255, 0), 2)
        for (x, y) in line:
            cv2.circle(temp, (x, y), POINT_RADIUS, (0, 255, 0), -1)
    elif len(line) == 1:
        cv2.circle(temp, line[0], POINT_RADIUS, (0, 255, 0), -1)

    # Label area
    area_label = {
        "wait": "WAITING",
        "cross": "CROSSING",
        "middle": "MIDDLE",
        "line": "COUNTING LINE"
    }
    cv2.putText(temp, f"Area aktif: {area_label[active_area]}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(temp, "TAB: Ganti Area | S: Simpan | Q: Keluar", (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

    cv2.imshow("Setup Area", temp)
    key = cv2.waitKey(1)

    if key == 9:  # TAB
        if active_area == "wait":
            active_area = "cross"
        elif active_area == "cross":
            active_area = "middle"
        elif active_area == "middle":
            active_area = "line"
        else:
            active_area = "wait"

    elif key == ord('s'):
        if len(area_wait) >= 3 and len(area_cross) >= 3 and len(area_middle) >= 3 and len(line) == 2:
            with open("config.json", "w") as f:
                json.dump({
                    "area_wait": area_wait,
                    "area_cross": area_cross,
                    "area_middle": area_middle,
                    "area_line": line
                }, f)
            print("✅ Semua area berhasil disimpan ke config.json")
        else:
            print("❌ Semua area harus lengkap:")
            print("   - wait, cross, middle: min 3 titik")
            print("   - line: harus 2 titik")

    elif key == ord('q'):
        break

cv2.destroyAllWindows()
