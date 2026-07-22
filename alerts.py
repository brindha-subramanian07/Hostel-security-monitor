"""
Alert dispatch - sends an email (with snapshot image attached) to all
authorised recipients defined in config.ALERT_RECIPIENTS.

To extend to SMS/WhatsApp/Push, add a similarly-shaped function here
(e.g. send_sms_alert using Twilio) and call it alongside send_email_alert
from app.py.
"""

import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime

import config


def send_email_alert(camera_name, snapshot_path, anomaly_type="Anomaly detected"):
    """Send an email alert with the snapshot attached. Fails silently-logged
    if SMTP is not configured, so it never crashes the detection loop."""
    try:
        msg = EmailMessage()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg["Subject"] = f"[Hostel CCTV Alert] {anomaly_type} - {camera_name}"
        msg["From"] = config.SMTP_USERNAME
        msg["To"] = ", ".join(config.ALERT_RECIPIENTS)
        msg.set_content(
            f"{anomaly_type}\n\n"
            f"Camera: {camera_name}\n"
            f"Time: {timestamp}\n\n"
            f"A snapshot is attached. Please check the live dashboard for more detail."
        )

        with open(snapshot_path, "rb") as f:
            msg.add_attachment(f.read(), maintype="image", subtype="jpeg",
                                filename="snapshot.jpg")

        context = ssl.create_default_context()
        with smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg)

        print(f"[alerts] Email sent for {camera_name} at {timestamp}")
        return True
    except Exception as e:
        print(f"[alerts] Failed to send email alert: {e}")
        return False
