from flask import Flask, render_template, request, redirect, url_for, session, Response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Resource, Api, reqparse, fields, marshal_with, abort
import cv2
import json
import numpy as np
import time
from shapely.geometry import Point, Polygon
from ultralytics import YOLO
from datetime import datetime
import requests

app = Flask(__name__)
app.secret_key = 'rahasia123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
api = Api(app)

# Dummy login
USER = {
    "username": "admin",
    "password": "admin123"
}

def get_weather_data():
    """Fetch real-time weather data from Open-Meteo API"""
    city = "Bandung"
    latitude, longitude = -6.9640, 107.6561

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}&"
        f"current_weather=true&hourly=relativehumidity_2m,weathercode&timezone=auto"
    )
    
    try:
        response = requests.get(url)
        data = response.json()

        current = data["current_weather"]
        hourly = data["hourly"]

        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        current_hour_str = now.strftime("%Y-%m-%dT%H:00")

        try:
            index = hourly["time"].index(current_hour_str)
            humidity = hourly["relativehumidity_2m"][index]
            weather_code = hourly["weathercode"][index]
        except ValueError:
            humidity = "N/A"
            weather_code = -1

        weather_map = {
            0: "Cerah",
            1: "Cerah Berawan",
            2: "Berawan",
            3: "Mendung",
            45: "Kabut",
            48: "Kabut Tebal",
            51: "Gerimis Ringan",
            53: "Gerimis",
            55: "Gerimis Berat",
            61: "Hujan Ringan",
            63: "Hujan Sedang",
            65: "Hujan Lebat",
        }

        weather_desc = weather_map.get(weather_code, "Tidak diketahui")

        return {
            'weather_desc': weather_desc,
            'temperature': current["temperature"],
            'humidity': humidity,
            'windspeed': current["windspeed"]
        }
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return {
            'weather_desc': 'Tidak tersedia',
            'temperature': 'N/A',
            'humidity': 'N/A',
            'windspeed': 'N/A'
        }

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        if uname == USER['username'] and pwd == USER['password']:
            session['user'] = uname
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Username atau password salah")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    # Get real-time weather data
    weather_data = get_weather_data()
    
    return render_template('dashboard.html', **weather_data)

@app.route('/api/weather')
def api_weather():
    """API endpoint for real-time weather data"""
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    weather_data = get_weather_data()
    return jsonify(weather_data)

@app.route('/video_feed')
def video_feed():
    if 'user' not in session:
        return redirect(url_for('login'))
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# Load Area dari config.json
with open("config.json", "r") as f:
    config = json.load(f)
area_wait = config["area_wait"]
area_cross = config["area_cross"]
polygon_wait = Polygon(area_wait)
polygon_cross = Polygon(area_cross)

# YOLO dan Video
model = YOLO("yolo11n.pt")
cap = cv2.VideoCapture("test_video4.mp4")
DISPLAY_WIDTH, DISPLAY_HEIGHT = 640, 640

waiting_ids = {}
green_light_start = None
no_detection_timer = None
lampu_hijau_pejalan = False
status = 0

def generate_frames():
    global waiting_ids, green_light_start, no_detection_timer, lampu_hijau_pejalan, status

    while True:
        success, frame = cap.read()
        if not success:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            continue

        frame = cv2.resize(frame, (DISPLAY_WIDTH, DISPLAY_HEIGHT))
        start_time = time.time()
        mask = np.zeros_like(frame[:, :, 0])
        cv2.fillPoly(mask, [np.array(area_wait, np.int32)], 255)
        cv2.fillPoly(mask, [np.array(area_cross, np.int32)], 255)
        masked_frame = cv2.bitwise_and(frame, frame, mask=mask)

        results = model.predict(frame, conf=0.25, classes=[0])
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
                    if elapsed >= 5:
                        lampu_hijau_pejalan = True
                        green_light_start = current_time
                        no_detection_timer = None

                elif polygon_cross.contains(center):
                    ada_di_crossing_area = True
                    no_detection_timer = None
                else:
                    waiting_ids.pop(id, None)

                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(annotated, (cx, cy), 4, (0, 0, 255), -1)

        if lampu_hijau_pejalan:
            status = 1
            if not ada_di_crossing_area:
                if no_detection_timer is None:
                    no_detection_timer = current_time
                elif current_time - no_detection_timer > 3:
                    lampu_hijau_pejalan = False
                    waiting_ids.clear()
                    no_detection_timer = None
        else:
            status = 0
            no_detection_timer = None

        cv2.polylines(annotated, [np.array(area_wait)], True, (0, 255, 255), 2)
        cv2.polylines(annotated, [np.array(area_cross)], True, (255, 255, 0), 2)

        if lampu_hijau_pejalan:
            cv2.rectangle(annotated, (20, 20), (160, 70), (0, 255, 0), -1)
            cv2.putText(annotated, "WALK", (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        else:
            cv2.rectangle(annotated, (20, 20), (160, 70), (0, 0, 255), -1)
            cv2.putText(annotated, "STOP", (30, 55), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        fps = 1 / (time.time() - start_time + 1e-6)
        cv2.putText(annotated, f"FPS: {fps:.2f}", (20, DISPLAY_HEIGHT - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        ret, buffer = cv2.imencode('.jpg', annotated)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

if __name__ == '__main__':
    app.run(debug=True)
