from flask import Flask, render_template, request
import psycopg2
from datetime import datetime
import os
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)

# Database connection
db_conn = psycopg2.connect(os.getenv("DATABASE_URL"))

# Image storage
IMAGE_DIR = "static/images"
os.makedirs(IMAGE_DIR, exist_ok=True)

@app.route('/')
def dashboard():
    cursor = db_conn.cursor()
    cursor.execute("SELECT timestamp, image_key, sign_type, confidence, lat, lon, speed FROM detections ORDER BY timestamp DESC LIMIT 5")
    detections = cursor.fetchall()
    cursor.close()
    return render_template('dashboard.html', detections=detections)

@socketio.on('connect')
def handle_connect():
    print("Client connected")

@app.route('/update', methods=['POST'])
def update_tracking():
    data = request.get_json()
    gps = data.get('gps', {})
    imu = data.get('imu', {})
    speed = data.get('speed', 0.0)

    # Emit real-time data to connected clients
    socketio.emit('tracking_update', {
        'lat': gps.get('lat'),
        'lon': gps.get('lon'),
        'speed': speed,
        'accel_x': imu.get('accel_x'),
        'accel_y': imu.get('accel_y'),
        'accel_z': imu.get('accel_z')
    })
    return {"status": "success"}, 200

@app.route('/detection', methods=['POST'])
def handle_detection():
    data = request.get_json()
    timestamp = data.get('timestamp')
    gps = data.get('gps', {})
    speed = data.get('speed', 0.0)
    image = data.get('image')
    detections = data.get('detections', [])

    # Save image
    image_key = f"{timestamp}.jpg"
    with open(os.path.join(IMAGE_DIR, image_key), "wb") as f:
        f.write(bytes.fromhex(image))

    # Store detection in database
    cursor = db_conn.cursor()
    for detection in detections:
        cursor.execute(
            """
            INSERT INTO detections (timestamp, image_key, sign_type, confidence, lat, lon, speed)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (timestamp, image_key, detection['sign_type'], detection['confidence'],
             gps.get('lat'), gps.get('lon'), speed)
        )
    db_conn.commit()
    cursor.close()

    return {"status": "success"}, 200

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)