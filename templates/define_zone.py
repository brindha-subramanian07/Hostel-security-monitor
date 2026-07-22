"""
Helper tool: click points on a real frame from one of your cameras to define
a restricted-zone polygon, and get the exact coordinates to paste into
config.py's "restricted_zones" for that camera.

Usage:
    python define_zone.py <camera_source>

Examples:
    python define_zone.py 0                              # laptop webcam
    python define_zone.py test_videos/intrusion.mp4       # a test video
    python define_zone.py "rtsp://user:pass@192.168.1.51:554/stream1"

Controls:
    Left click   - add a point to the polygon
    'u'          - undo last point
    'r'          - reset (clear all points)
    's'          - save/print the polygon and continue defining another one
    'q' or Esc   - quit
"""

import sys
import numpy as np
import cv2

points = []
all_zones = []


def on_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append((x, y))


def main():
    if len(sys.argv) < 2:
        print("Usage: python define_zone.py <camera_source>")
        sys.exit(1)

    source = sys.argv[1]
    if source.isdigit():
        source = int(source)

    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"Could not open source: {source}")
        sys.exit(1)

    ok, frame = cap.read()
    if not ok:
        print("Could not read a frame from that source.")
        sys.exit(1)
    frame = cv2.resize(frame, (640, 360))

    window_name = "Define restricted zone - click points, 's' to save, 'q' to quit"
    cv2.namedWindow(window_name)
    cv2.setMouseCallback(window_name, on_click)

    print("\nClick points around the restricted area on the image window.")
    print("Press 's' to save that polygon and start another, 'q' to finish.\n")

    while True:
        display = frame.copy()
        for p in points:
            cv2.circle(display, p, 4, (0, 0, 255), -1)
        if len(points) > 1:
            cv2.polylines(display, [np.array(points, dtype=int)], False, (0, 165, 255), 2)

        cv2.imshow(window_name, display)
        key = cv2.waitKey(20) & 0xFF

        if key == ord('u') and points:
            points.pop()
        elif key == ord('r'):
            points.clear()
        elif key == ord('s'):
            if len(points) >= 3:
                all_zones.append(list(points))
                print("Saved zone:", list(points))
                points.clear()
            else:
                print("Need at least 3 points to save a polygon.")
        elif key == ord('q') or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()

    if all_zones:
        print("\nPaste this into the camera's entry in config.py:\n")
        print('    "restricted_zones": [')
        for zone in all_zones:
            print(f"        {zone},")
        print("    ],")
    else:
        print("\nNo zones saved.")


if __name__ == "__main__":
    main()
