"""
Behavior detection logic.

Uses a YOLOv8 person detector (instead of plain motion detection) so the
system can distinguish "a person is here" from "a curtain moved" - and then
applies rule-based logic on top of the detected people to classify WHAT kind
of anomaly is happening:

  - "Unauthorized entry after curfew hours" - a person seen on a
    curfew-monitored camera outside ACTIVE_HOURS
  - "Intruder detected"                     - a person seen on a camera
    marked intrusion_zone=True (e.g. locked storeroom, terrace)
  - "Restricted area intrusion"              - a person's position falls
    inside a defined restricted_zones polygon
  - "Loitering detected"                     - a person has remained in
    frame longer than loitering_seconds
  - "Crowd detected"                         - person count on a camera
    exceeds crowd_threshold

Each anomaly type has its own alert cooldown per camera so one continuous
event doesn't spam repeated alerts.

The YOLO model weights (yolov8n.pt, ~6MB) download automatically the first
time this runs and are then cached locally - the first startup needs
internet access, later runs work offline.
"""

import time
import cv2
import numpy as np
from ultralytics import YOLO

import config

_MODEL = None


def get_model():
    """Load the YOLO model once and share it across all camera threads."""
    global _MODEL
    if _MODEL is None:
        _MODEL = YOLO("yolov8n.pt")
    return _MODEL


def point_in_polygon(point, polygon):
    poly = np.array(polygon, dtype=np.int32)
    return cv2.pointPolygonTest(poly, point, False) >= 0


class TrackedPerson:
    """Minimal centroid tracker entry - just enough to measure dwell time
    for loitering detection. Not a full multi-object tracker, but good
    enough for a single-camera, low-frame-rate setup."""
    def __init__(self, pid, centroid):
        self.id = pid
        self.centroid = centroid
        self.first_seen = time.time()
        self.last_seen = time.time()
        self.alerted_loitering = False


class AnomalyDetector:
    def __init__(self, camera_id, camera_cfg=None):
        self.camera_id = camera_id
        self.cfg = camera_cfg or {}
        self.tracked = {}
        self.next_id = 0
        self.last_alert_time = {}   # anomaly_type -> timestamp, for per-type cooldown

    def _within_curfew_hours(self):
        window = config.ACTIVE_HOURS
        if not window:
            return False
        hour = time.localtime().tm_hour
        start, end = window["start"], window["end"]
        if start <= end:
            return start <= hour < end
        return hour >= start or hour < end   # wraps past midnight, e.g. 23 -> 6

    def _cooldown_ok(self, anomaly_type):
        now = time.time()
        last = self.last_alert_time.get(anomaly_type, 0)
        if now - last >= config.ALERT_COOLDOWN_SECONDS:
            self.last_alert_time[anomaly_type] = now
            return True
        return False

    def _update_tracks(self, centroids):
        """Very simple nearest-centroid matching frame-to-frame."""
        used = set()
        for c in centroids:
            best_id, best_dist = None, 90  # max pixel distance to count as "same person"
            for pid, tp in self.tracked.items():
                if pid in used:
                    continue
                d = np.hypot(tp.centroid[0] - c[0], tp.centroid[1] - c[1])
                if d < best_dist:
                    best_dist, best_id = d, pid
            if best_id is not None:
                self.tracked[best_id].centroid = c
                self.tracked[best_id].last_seen = time.time()
                used.add(best_id)
            else:
                pid = self.next_id
                self.next_id += 1
                self.tracked[pid] = TrackedPerson(pid, c)
                used.add(pid)

        # drop people not seen recently (left the frame)
        stale = [pid for pid, tp in self.tracked.items() if time.time() - tp.last_seen > 3]
        for pid in stale:
            del self.tracked[pid]

    def analyze(self, frame):
        """
        Runs detection + rule logic on a single frame.
        Returns (anomalies: list[str], annotated_frame, boxes: list[(x1,y1,x2,y2)])
        `anomalies` may contain zero, one, or multiple labels for this frame.
        """
        model = get_model()
        results = model.predict(frame, classes=[0], conf=config.PERSON_CONFIDENCE,
                                 verbose=False)[0]   # class 0 = "person" in COCO

        boxes = []
        centroids = []
        for b in results.boxes:
            x1, y1, x2, y2 = map(int, b.xyxy[0])
            boxes.append((x1, y1, x2, y2))
            centroids.append(((x1 + x2) // 2, (y1 + y2) // 2))
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 0), 2)

        self._update_tracks(centroids)

        anomalies = []

        # --- Curfew: any person on a curfew-monitored camera outside hours ---
        if boxes and self.cfg.get("curfew_monitored", True) and self._within_curfew_hours():
            if self._cooldown_ok("curfew"):
                anomalies.append("Unauthorized entry after curfew hours")

        # --- Intrusion zone: ANY person, ANY time (e.g. locked storeroom) ---
        if boxes and self.cfg.get("intrusion_zone", False):
            if self._cooldown_ok("intrusion"):
                anomalies.append("Intruder detected")

        # --- Restricted polygon zones within the frame ---
        zones = self.cfg.get("restricted_zones")
        if zones:
            zone_hit = False
            for c in centroids:
                for zone in zones:
                    if point_in_polygon(c, zone):
                        zone_hit = True
                        break
                if zone_hit:
                    break
            if zone_hit and self._cooldown_ok("restricted_zone"):
                anomalies.append("Restricted area intrusion")
            if zones:
                for zone in zones:
                    pts = np.array(zone, dtype=np.int32)
                    cv2.polylines(frame, [pts], True, (0, 165, 255), 2)

        # --- Crowd detection ---
        crowd_threshold = self.cfg.get("crowd_threshold", config.CROWD_THRESHOLD)
        if len(boxes) >= crowd_threshold and self._cooldown_ok("crowd"):
            anomalies.append("Crowd detected")

        # --- Loitering: someone staying too long ---
        loiter_seconds = self.cfg.get("loitering_seconds", config.LOITERING_SECONDS)
        for pid, tp in self.tracked.items():
            dwell = time.time() - tp.first_seen
            if dwell >= loiter_seconds and not tp.alerted_loitering:
                tp.alerted_loitering = True
                if self._cooldown_ok("loitering"):
                    anomalies.append("Loitering detected")

        for i, label in enumerate(anomalies):
            cv2.putText(frame, label, (10, 30 + 25 * i), cv2.FONT_HERSHEY_SIMPLEX,
                        0.65, (0, 0, 255), 2)

        return anomalies, frame, boxes
