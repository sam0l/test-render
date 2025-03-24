from flask import Flask, render_template, request, jsonify
import psycopg2
from datetime import datetime
import os
import time

app = Flask(__name__)

# Database connection
db_conn = psycopg2.connect(os.getenv("DATABASE_URL"))
IMAGE_DIR = "static/images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# In-memory state for tracking
latest_tracking = {"gps": {"lat": None, "lon": None}, "speed": 0.0}
drives = []
current_path = []
drive_start_time = None
stop_timer = None

SPEED_THRESHOLD = 15  # kph
STOP_DURATION = 30   # seconds

@app.route('/')
def dashboard():
    cursor = db_conn.cursor()
    cursor.execute("SELECT timestamp, image_key, speed, lat, lon, violation FROM detections ORDER BY timestamp DESC")
    detections = cursor.fetchall()
    cursor.close()
    return render_template('dashboard.html', drives=drives, detections=detections)

@app.route('/update', methods=['POST'])
def update_tracking():
    global latest_tracking, drives, current_path, drive_start_time, stop_timer
    data = request.get_json()
    gps = data.get('gps', {'lat': None, 'lon': None})
    speed = data.get('speed', 0.0)
    frame = data.get('frame')
    detections = data.get('detections', [])

    # Update latest tracking
    latest_tracking = {'gps': gps, 'speed': speed}

    # Handle drive path
    if gps.get('lat') and gps.get('lon'):
        current_path.append((gps['lat'], gps['lon']))

        if speed > 0 and drive_start_time is None:  # Start a new drive
            drive_start_time = time.time()
        elif speed <= SPEED_THRESHOLD and drive_start_time:
            if stop_timer is None:
                stop_timer = time.time()
            elif time.time() - stop_timer >= STOP_DURATION:  # End drive
                duration = time.time() - drive_start_time
                avg_speed = sum(p[1] for p in current_path if p[1] is not None) / max(1, len(current_path)) if drives else speed
                drives.append({
                    'start_coords': current_path[0],
                    'end_coords': current_path[-1],
                    'path': current_path.copy(),
                    'avg_speed': avg_speed,
                    'duration': duration
                })
                current_path = []
                drive_start_time = None
                stop_timer = None
        else:
            stop_timer = None

    # Handle traffic sign detections
    if frame and detections:
        timestamp = datetime.now().isoformat()
        image_key = f"{timestamp}.jpg"
        with open(os.path.join(IMAGE_DIR, image_key), "wb") as f:
            f.write(bytes.fromhex(frame))
        cursor = db_conn.cursor()
        for det in detections:
            is_speed_limit = 'speed' in det.get('sign_type', '').lower()
            limit = float(''.join(filter(str.isdigit, det.get('sign_type', '0'))) or 0)
            violation = is_speed_limit and speed > limit
            cursor.execute(
                "INSERT INTO detections (timestamp, image_key, speed, lat, lon, violation) VALUES (%s, %s, %s, %s, %s, %s)",
                (timestamp, image_key, speed, gps.get('lat'), gps.get('lon'), violation)
            )
        db_conn.commit()
        cursor.close()

    return {"status": "success"}, 200

@app.route('/latest', methods=['GET'])
def get_latest():
    return jsonify({'tracking': latest_tracking, 'path': current_path, 'drives': drives})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))