from flask import Flask, request, jsonify, render_template
import psycopg2
from datetime import datetime
import os

app = Flask(__name__)

# Database connection (Render provides a connection URL)
db_conn = psycopg2.connect(os.getenv("DATABASE_URL"))

# Directory for images
IMAGE_DIR = "static/images"
os.makedirs(IMAGE_DIR, exist_ok=True)

@app.route('/upload', methods=['POST'])
def upload_data():
    data = request.get_json()
    gps = data.get('gps', {})
    imu = data.get('imu', {})
    image = data.get('image')  # Base64-encoded
    detections = data.get('detections', [])

    # Insert GPS and IMU into PostgreSQL
    cursor = db_conn.cursor()
    cursor.execute(
        """
        INSERT INTO vehicle_logs (timestamp, lat, lon, accel_x, accel_y, accel_z)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (datetime.now(), gps.get('lat'), gps.get('lon'), imu.get('accel_x'), imu.get('accel_y'), imu.get('accel_z'))
    )
    db_conn.commit()

    # Save image locally
    image_key = f"{datetime.now().isoformat()}.jpg"
    with open(os.path.join(IMAGE_DIR, image_key), "wb") as f:
        f.write(bytes.fromhex(image))  # Assuming hex-encoded; adjust if base64

    # Store detection metadata
    for detection in detections:
        cursor.execute(
            """
            INSERT INTO detections (timestamp, image_key, sign_type, confidence)
            VALUES (%s, %s, %s, %s)
            """,
            (datetime.now(), image_key, detection['sign_type'], detection['confidence'])
        )
    db_conn.commit()
    cursor.close()

    return jsonify({"status": "success"}), 200

@app.route('/')
def dashboard():
    cursor = db_conn.cursor()
    cursor.execute("SELECT timestamp, lat, lon, accel_x, accel_y, accel_z FROM vehicle_logs ORDER BY timestamp DESC LIMIT 10")
    logs = cursor.fetchall()
    cursor.execute("SELECT timestamp, image_key, sign_type, confidence FROM detections ORDER BY timestamp DESC LIMIT 5")
    detections = cursor.fetchall()
    cursor.close()
    return render_template('dashboard.html', logs=logs, detections=detections)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)