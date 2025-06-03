from ultralytics import YOLO

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# Asumsi fungsi send_email_alert_with_image sudah didefinisikan
def send_email_alert_with_image(image_path, detected_class, location):
    sender = "aziszuhrip354@gmail.com"
    password = "jgtdswqvaduzmzma"  # Gunakan App Password
    receiver = "ajisbhakun354@gmail.com"

    subject = f"ALERT: Multiple '{detected_class}' Detected di {location}"
    body = f"Terdeteksi seseorang tanpa {detected_class} beberapa kali di lokasi {location} (simulasi video). Berikut adalah gambar terakhir yang terdeteksi."

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = receiver
    msg.attach(MIMEText(body, "plain"))

    with open(image_path, "rb") as f:
        img_attach = MIMEApplication(f.read(), _subtype="jpg")
        img_attach.add_header("Content-Disposition", "attachment", filename="capture.jpg")
        msg.attach(img_attach)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.send_message(msg)
        print(f"✅ Email dengan gambar terkirim untuk '{detected_class}' dari '{location}' (simulasi)!", flush=True)
    except Exception as e:
        print(f"❌ Gagal kirim email untuk '{detected_class}' dari '{location}' (simulasi): {e}", flush=True)
