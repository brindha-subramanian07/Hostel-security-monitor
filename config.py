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
#   - a video file path, e.g. "test_videos/intrusion.mp4"
#   - an RTSP url string, e.g. "rtsp://user:pass@192.168.1.50:554/stream1"
#
# Per-camera behavior flags (all optional - sensible defaults apply if omitted):
#   "curfew_monitored"  : bool  - alert on ANY person detected outside ACTIVE_HOURS
#                                  (use for entrances / corridors that should be
#                                  empty overnight). Default True.
#   "intrusion_zone"    : bool  - treat ANY person detected here, at ANY time,
#                                  as an intrusion (e.g. a locked storeroom,
#                                  terrace, roof access). Default False.
#   "restricted_zones"  : list of polygons - areas within the frame that are
#                                  off-limits (e.g. a female floor's staircase
#                                  landing on a male-floor camera). Each polygon
#                                  is a list of (x, y) pixel points. Use
#                                  define_zone.py to find these coordinates by
#                                  clicking on a real frame from that camera.
#   "crowd_threshold"   : int   - people count that counts as "a crowd" for
#                                  this camera specifically. Falls back to
#                                  CROWD_THRESHOLD below if omitted.
#   "loitering_seconds" : int   - seconds a person can stay before it's flagged
#                                  as loitering. Falls back to
#                                  LOITERING_SECONDS below if omitted.
CAMERAS = [
    {
        "id": "cam1",
        "name": "Main Entrance",
        "source": 0,
        "curfew_monitored": True,
    },
    {
        "id": "cam2",
        "name": "Corridor - Floor 1",
        "source": "rtsp://user:pass@192.168.1.51:554/stream1",
        "curfew_monitored": True,
        "loitering_seconds": 45,
    },
    {
        "id": "cam3",
        "name": "Common Room",
        "source": "rtsp://user:pass@192.168.1.52:554/stream1",
        "curfew_monitored": False,   # common room is fine to be occupied late
        "crowd_threshold": 6,
    },
]

# ---------------------------------------------------------------------------
# DETECTION SETTINGS
# ---------------------------------------------------------------------------
# Minimum confidence (0-1) for a YOLO person detection to count.
PERSON_CONFIDENCE = 0.45

# Default "a crowd" person-count threshold, used unless a camera overrides it.
CROWD_THRESHOLD = 4

# Default loitering duration (seconds) a person must remain in frame before
# it's flagged, used unless a camera overrides it.
LOITERING_SECONDS = 60

# Seconds to wait after an alert before the SAME anomaly type on the SAME
# camera can fire again (prevents spamming one continuous event).
ALERT_COOLDOWN_SECONDS = 60

# Frames per second target for processing (lower = less CPU usage - useful
# since YOLO is heavier per-frame than plain motion detection).
PROCESS_FPS = 5

# Curfew / restricted hours (24h format). Any camera with "curfew_monitored":
# True will alert if a person is seen during this window. Set to None to
# disable curfew checking globally.
ACTIVE_HOURS = {"start": 23, "end": 6}   # 11 PM - 6 AM

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
