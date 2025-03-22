from flask import Flask, render_template, request, jsonify
import psycopg2
from datetime import datetime
import os

app = Flask(__name__)

# Database connection
db_conn = psycopg2.connect(os.getenv("DATABASE_URL"))

# Image storage
IMAGE_DIR = "static/images"
os.makedirs(IMAGE_DIR, exist_ok=True)

# Store latest tracking data
latest_tracking = {}

@app.route('/')
def dashboard():
    cursor = db_conn.cursor()
    cursor.execute("SELECT timestamp, image_key, lat, lon FROM frames ORDER BY timestamp DESC LIMIT 1")
    latest_frame = cursor.fetchone()
    cursor.close()
    return render_template('dashboard.html', latest_frame=latest_frame)

@app.route('/update', methods=['POST'])
def update_tracking():
    global latest_tracking
    data = request.get_json()
    gps = data.get('gps', {})
    frame = data.get('frame')

    if frame:  # Only process if frame is present
        timestamp = datetime.now().isoformat()
        image_key = f"{timestamp}.jpg"
        with open(os.path.join(IMAGE_DIR, image_key), "wb") as f:
            f.write(bytes.fromhex(frame))

        # Store in database
        cursor = db_conn.cursor()
        cursor.execute(
            """
            INSERT INTO frames (timestamp, image_key, lat, lon)
            VALUES (%s, %s, %s, %s)
            """,
            (timestamp, image_key, gps.get('lat'), gps.get('lon'))
        )
        db_conn.commit()
        cursor.close()

        # Update latest tracking
        latest_tracking = {"gps": gps, "image_key": image_key}

    return {"status": "success"}, 200

@app.route('/latest', methods=['GET'])
def get_latest():
    return jsonify(latest_tracking)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv("PORT", 5000)))