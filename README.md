# Hostel CCTV Abnormal Activity Monitor

A Flask + OpenCV web application that streams hostel CCTV camera feeds,
detects abnormal activity (motion-based anomaly detection), logs alerts,
and emails snapshots to authorised staff (warden/security) in real time.

## How it works

```
IP/USB Cameras --> CameraWorker threads (OpenCV) --> AnomalyDetector
                                   |                        |
                                   |                 anomaly found?
                                   v                        v
                           MJPEG stream to        snapshot saved + logged
                           web dashboard           to SQLite + emailed to
                                                    authorised recipients
```

- Each camera runs in its own background thread and is read continuously.
- `detection.py` uses background subtraction (MOG2) to flag large, sustained
  motion blobs — a simple, dependency-light way to catch unusual activity
  (intrusion, altercation, crowding, after-hours movement).
- When N consecutive frames show significant motion (and, optionally, it's
  within your configured "quiet hours"), it's logged as an anomaly, a
  snapshot is saved, and an email alert is sent — with a cooldown so you
  don't get spammed.
- The dashboard (`/`) shows live feeds + a running alert list, and requires
  login.

## Step 1 — Install prerequisites

- Python 3.9+
- pip

```bash
cd hostel-cctv-monitor
python -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 2 — Configure your cameras

Open `config.py` and edit the `CAMERAS` list:

```python
CAMERAS = [
    {"id": "cam1", "name": "Main Entrance", "source": 0},                     # USB webcam
    {"id": "cam2", "name": "Corridor - Floor 1", "source": "rtsp://user:pass@192.168.1.51:554/stream1"},
]
```

- `source: 0` (or 1, 2...) = a locally attached USB webcam.
- `source: "rtsp://..."` = an IP camera's RTSP stream. Check your camera/NVR
  manual for the exact RTSP URL format (brand-specific, e.g. Hikvision,
  Dahua, TP-Link).
- Most CCTV/NVR systems expose RTSP even if you normally view them through
  a vendor app — look in the NVR's network settings.

## Step 3 — Configure detection sensitivity

Still in `config.py`:

- `MIN_MOTION_AREA` — raise this if you get false alerts from shadows, tree
  branches outside a window, curtains, etc.
- `CONSECUTIVE_FRAMES_THRESHOLD` — how many frames in a row must show motion
  before it counts as an anomaly (filters single-frame noise).
- `ACTIVE_HOURS` — restrict alerting to certain hours (e.g. only flag motion
  in a corridor between 11 PM–6 AM). Set to `None` to monitor 24/7.

## Step 4 — Configure email alerts

In `config.py` (or better, via environment variables so you don't commit
secrets):

```bash
export SMTP_USERNAME="your_alert_account@gmail.com"
export SMTP_PASSWORD="your_16_char_app_password"   # Gmail: create an "App Password", not your login password
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(16))')"
export DASHBOARD_USERNAME="admin"
export DASHBOARD_PASSWORD="a_strong_password"
```

Add each authorised person's email to `ALERT_RECIPIENTS` in `config.py`.

## Step 5 — Run it

```bash
python app.py
```

Open **http://localhost:5000**, log in with your dashboard credentials, and
you'll see the live camera grid plus the alert panel updating automatically.

## Step 6 — (Optional) Improve detection accuracy

The default motion-based detector is a good, fast baseline but can't tell
the difference between "a person" and "a moving curtain." To make it smarter:

1. `pip install ultralytics` (YOLOv8)
2. In `detection.py`, at the marked **SWAP POINT**, run a person detector
   on the frame instead of / in addition to background subtraction, so
   alerts trigger on "person detected in a restricted zone" rather than any
   motion.
3. For specific behaviors (fall detection, fighting/violence detection,
   loitering time limits, restricted-zone intrusion with drawn polygons),
   you'd extend `AnomalyDetector.analyze()` with that specific logic —
   these typically need a pose-estimation or action-recognition model
   (e.g. MediaPipe Pose, or a pretrained violence-detection model) rather
   than plain motion detection.

## Step 7 — (Optional) Add SMS/WhatsApp alerts

In `alerts.py`, add a `send_sms_alert()` function using a provider like
Twilio, and call it from `app.py`'s `_handle_anomaly()` alongside
`send_email_alert()`.

## Step 8 — Deploying for real use

For anything beyond a local test:

- **Run behind a real WSGI server** (e.g. `gunicorn -w 1 -k gthread
  --threads 8 -b 0.0.0.0:5000 app:app`) instead of Flask's dev server.
  Use only 1 worker process (or a shared broker) since camera threads live
  in-process; scaling to multiple workers needs a different architecture
  (e.g. a separate capture service publishing frames via Redis/RTMP).
- **Put it behind HTTPS** (nginx + Let's Encrypt, or a reverse proxy) —
  never expose a camera dashboard over plain HTTP.
- **Replace the simple login** with proper authentication (hashed passwords
  in a DB, or SSO) before giving multiple staff accounts.
- **Run cameras on a dedicated/segmented network (VLAN)**, not the general
  guest Wi-Fi.
- Consider a process manager (systemd, Docker + restart policy) so it
  survives reboots and camera disconnects.

## Important: privacy & legal considerations

Before deploying CCTV monitoring in a hostel (a residential space), check
what's required in your jurisdiction/institution — this typically includes:

- **No cameras in private areas**: rooms, bathrooms, changing areas.
- **Signage/notice**: residents should be informed cameras are in use and
  roughly what's monitored.
- **Data retention limits**: don't keep snapshots/footage indefinitely —
  define a retention period and auto-delete after it (you can add a cron
  job that purges `static/snapshots/` and old DB rows past N days).
- **Access control**: only authorised staff (warden/security) should be
  able to view feeds or alert history — this is why the dashboard requires
  login; consider adding per-user accounts and an access log too.
- **Institutional/legal approval**: many colleges/universities require
  administration or legal sign-off before deploying any monitoring system
  on students. Check your institution's policy and local law before going
  live.

## Project structure

```
hostel-cctv-monitor/
├── app.py              # Flask app: routes, camera threads, DB, streaming
├── detection.py         # AnomalyDetector (motion-based, swappable for ML model)
├── alerts.py             # Email alert sending
├── config.py              # Cameras, thresholds, SMTP, login credentials
├── requirements.txt
├── templates/
│   ├── index.html        # Dashboard
│   └── login.html
└── static/
    ├── style.css
    ├── script.js
    └── snapshots/         # Saved anomaly snapshots (created at runtime)
```
