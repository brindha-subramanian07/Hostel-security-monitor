"""
Motion / anomaly detection logic.

This starter implementation uses background subtraction (MOG2) to flag
unusual movement - a practical, dependency-light way to catch things like:
  - someone entering a restricted area after hours
  - a sudden crowd / scuffle (large connected motion blob)
  - loitering / unexpected activity in a corridor at night

For production use, you can swap `AnomalyDetector.analyze()` to also run a
person-detector (e.g. YOLOv8) so alerts are triggered specifically on
"person detected" rather than any motion (pets, curtains, lighting changes).
That swap point is marked below.
"""

import time
import cv2
import numpy as np

import config


class AnomalyDetector:
    def __init__(self, camera_id):
        self.camera_id = camera_id
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=300, varThreshold=40, detectShadows=True
        )
        self.consecutive_motion_frames = 0
        self.last_alert_time = 0

    def _within_active_hours(self):
        window = config.ACTIVE_HOURS
        if not window:
            return True
        hour = time.localtime().tm_hour
        start, end = window["start"], window["end"]
        if start <= end:
            return start <= hour < end
        # window wraps past midnight, e.g. 23 -> 6
        return hour >= start or hour < end

    def analyze(self, frame):
        """
        Runs detection on a single frame.
        Returns (is_anomaly: bool, annotated_frame, boxes: list[(x,y,w,h)])
        """
        boxes = []
        fg_mask = self.bg_subtractor.apply(frame)
        fg_mask = cv2.medianBlur(fg_mask, 5)
        _, fg_mask = cv2.threshold(fg_mask, 250, 255, cv2.THRESH_BINARY)
        fg_mask = cv2.dilate(fg_mask, np.ones((5, 5), np.uint8), iterations=2)

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        significant_motion = False

        for c in contours:
            area = cv2.contourArea(c)
            if area >= config.MIN_MOTION_AREA:
                significant_motion = True
                x, y, w, h = cv2.boundingRect(c)
                boxes.append((x, y, w, h))
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # ------------------------------------------------------------------
        # SWAP POINT: replace the block above (or augment it) with a person/
        # object detector for higher precision, e.g.:
        #
        #   results = yolo_model(frame)
        #   boxes = [b for b in results.boxes if b.cls == PERSON_CLASS]
        #   significant_motion = len(boxes) > 0
        # ------------------------------------------------------------------

        if significant_motion and self._within_active_hours():
            self.consecutive_motion_frames += 1
        else:
            self.consecutive_motion_frames = 0

        is_anomaly = False
        if self.consecutive_motion_frames >= config.CONSECUTIVE_FRAMES_THRESHOLD:
            now = time.time()
            if now - self.last_alert_time >= config.ALERT_COOLDOWN_SECONDS:
                is_anomaly = True
                self.last_alert_time = now
                self.consecutive_motion_frames = 0

        if boxes:
            label = "ANOMALY DETECTED" if is_anomaly else "Motion"
            cv2.putText(frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (0, 0, 255), 2)

        return is_anomaly, frame, boxes
