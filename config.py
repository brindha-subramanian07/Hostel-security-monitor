"""
Central configuration for the Hostel CCTV Monitoring System.
Edit the values below to match your environment.
"""

import os

# ---------------------------------------------------------------------------
# CAMERAS
# ---------------------------------------------------------------------------
# "source" can be:
#   - an integer (0, 1, ...) for a locally attached USB webcam
#   - an RTSP url string, e.g. "rtsp://user:pass@192.168.1.50:554/stream1"
#   - an HTTP MJPEG url from an IP camera
CAMERAS = [
    {"id": "cam1", "name": "Main Entrance", "source": 0},
]

# ---------------------------------------------------------------------------
# DETECTION SETTINGS
# ---------------------------------------------------------------------------
# Minimum contour area (in pixels) to be considered "significant motion".
# Increase this if the system is too sensitive (e.g. picks up shadows/curtains).
MIN_MOTION_AREA = 4500

# Number of consecutive "motion" frames required before we call it an anomaly.
# Helps filter out single-frame noise/flicker.
CONSECUTIVE_FRAMES_THRESHOLD = 8

# Seconds to wait after an alert before the same camera can alert again.
ALERT_COOLDOWN_SECONDS = 60

# Frames per second target for processing (lower = less CPU usage).
PROCESS_FPS = 8

# Optional: restrict detection to certain hours (24h format). Set to None to disable.
# Example: only actively alert between 11 PM and 6 AM (typical "quiet hours" for a hostel)
ACTIVE_HOURS = {"start": 23, "end": 6}   # set to None to monitor 24/7

# ---------------------------------------------------------------------------
# ALERTING (EMAIL)
# ---------------------------------------------------------------------------
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "your_alert_account@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "your_app_password")  # use an app password, not your real password

ALERT_RECIPIENTS = [
    "warden@example.com",
    "security@example.com",
]

# ---------------------------------------------------------------------------
# DASHBOARD LOGIN (very simple - replace with proper auth/SSO in production)
# ---------------------------------------------------------------------------
DASHBOARD_USERNAME = os.environ.get("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "change_me_123")

SECRET_KEY = os.environ.get("SECRET_KEY", "replace-this-with-a-random-secret-key")

# ---------------------------------------------------------------------------
# STORAGE
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "alerts.db")
SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "static", "snapshots")
