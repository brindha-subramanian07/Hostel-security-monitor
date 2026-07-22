"""
Hostel CCTV Monitoring System - main Flask application.

Run with:  python app.py
Then open: http://localhost:5000
"""

import os
import time
import sqlite3
import threading
import webbrowser
from datetime import datetime
from functools import wraps

import cv2
from flask import (
    Flask, Response, render_template, request, redirect,
    url_for, session, jsonify, flash
)

import config
from detection import AnomalyDetector
from alerts import send_email_alert

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

os.makedirs(config.SNAPSHOT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Shared state: one CameraWorker per configured camera, running in its own
# background thread, continuously producing the latest annotated JPEG frame.
# ---------------------------------------------------------------------------

class CameraWorker:
    def __init__(self, cam_cfg):
        self.id = cam_cfg["id"]
        self.name = cam_cfg["name"]
        self.source = cam_cfg["source"]
        self.detector = AnomalyDetector(self.id, cam_cfg)
        self.latest_jpeg = None
        self.lock = threading.Lock()
        self.running = True
        self.connected = False
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def _run(self):
        delay = 1.0 / max(config.PROCESS_FPS, 1)
        while self.running:
            cap = cv2.VideoCapture(self.source)
            if not cap.isOpened():
                self.connected = False
                print(f"[{self.id}] Could not open source '{self.source}', retrying in 5s...")
                time.sleep(5)
                continue

            self.connected = True
            while self.running:
                ok, frame = cap.read()
                if not ok:
                    print(f"[{self.id}] Lost stream, reconnecting...")
                    self.connected = False
                    break

                frame = cv2.resize(frame, (640, 360))
                anomalies, annotated, boxes = self.detector.analyze(frame)

                ok, buf = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ok:
                    with self.lock:
                        self.latest_jpeg = buf.tobytes()

                for anomaly_type in anomalies:
                    self._handle_anomaly(annotated, anomaly_type)

                time.sleep(delay)

            cap.release()

    def _handle_anomaly(self, annotated_frame, anomaly_type):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_type = anomaly_type.lower().replace(" ", "_")
        filename = f"{self.id}_{safe_type}_{timestamp}.jpg"
        path = os.path.join(config.SNAPSHOT_DIR, filename)
        cv2.imwrite(path, annotated_frame)

        log_alert(self.id, self.name, filename, anomaly_type)

        # Send email in a separate thread so it never blocks the video loop
        threading.Thread(
            target=send_email_alert,
            args=(self.name, path, anomaly_type),
            daemon=True
        ).start()

    def get_jpeg(self):
        with self.lock:
            return self.latest_jpeg


workers = {}


def init_workers():
    for cam_cfg in config.CAMERAS:
        w = CameraWorker(cam_cfg)
        w.start()
        workers[cam_cfg["id"]] = w


# ---------------------------------------------------------------------------
# Database (SQLite) for alert history
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id TEXT NOT NULL,
            camera_name TEXT NOT NULL,
            snapshot_file TEXT NOT NULL,
            anomaly_type TEXT NOT NULL DEFAULT 'Anomaly detected',
            created_at TEXT NOT NULL,
            acknowledged INTEGER DEFAULT 0
        )
    """)
    # Safe to run even if the column already exists from a previous version
    try:
        conn.execute("ALTER TABLE alerts ADD COLUMN anomaly_type TEXT NOT NULL DEFAULT 'Anomaly detected'")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.commit()
    conn.close()


def log_alert(camera_id, camera_name, snapshot_file, anomaly_type):
    conn = get_db()
    conn.execute(
        "INSERT INTO alerts (camera_id, camera_name, snapshot_file, anomaly_type, created_at) VALUES (?, ?, ?, ?, ?)",
        (camera_id, camera_name, snapshot_file, anomaly_type, datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Auth (simple session-based login; swap for SSO/proper auth in production)
# ---------------------------------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == config.DASHBOARD_USERNAME and password == config.DASHBOARD_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        flash("Invalid credentials")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Dashboard routes
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def index():
    cameras = [{"id": w.id, "name": w.name} for w in workers.values()]
    return render_template("index.html", cameras=cameras)


def mjpeg_generator(worker):
    while True:
        frame = worker.get_jpeg()
        if frame is not None:
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        time.sleep(1.0 / max(config.PROCESS_FPS, 1))


@app.route("/video_feed/<camera_id>")
@login_required
def video_feed(camera_id):
    worker = workers.get(camera_id)
    if not worker:
        return "Camera not found", 404
    return Response(mjpeg_generator(worker),
                     mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/alerts")
@login_required
def api_alerts():
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM alerts ORDER BY id DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/alerts/<int:alert_id>/ack", methods=["POST"])
@login_required
def ack_alert(alert_id):
    conn = get_db()
    conn.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


@app.route("/api/camera_status")
@login_required
def camera_status():
    return jsonify([
        {"id": w.id, "name": w.name, "connected": w.connected}
        for w in workers.values()
    ])


if __name__ == "__main__":
    init_db()
    init_workers()
    # Open the dashboard automatically once the server is up
    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
