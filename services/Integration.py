import requests
import json
import os
import platform
from queue import Queue
import threading

# Konfigurasi API
API_BASE_URL = "https://ppe-detection.azuhri-dev.com/api"  # Ganti dengan base URL API Anda
ALERT_ENDPOINT = "/violation"      # Ganti dengan endpoint API untuk mengirim alert

# Fungsi untuk mengirim alert via API
def play_alarm_sound():
    """
    Memainkan suara alert pelanggaran dari file alarm/alert-alarm.mp3 (cross-platform).
    """
    alarm_path = "/Users/aziszuhrip354/Desktop/workspace/ppe.detection.worker/alarm/alert-alarm.mp3"
    try:
        if platform.system() == "Darwin":  # macOS
            os.system(f'afplay "{alarm_path}"')
        elif platform.system() == "Windows":
            import subprocess
            subprocess.Popen(['start', '', alarm_path], shell=True)
        else:  # Linux
            os.system(f'paplay "{alarm_path}" || mpg123 "{alarm_path}" || play "{alarm_path}"')
    except Exception as e:
        print(f"❌ Error playing alert sound: {e}")

# Queue untuk menyimpan alert yang akan dikirim
alert_queue = Queue()

def alert_worker():
    while True:
        item = alert_queue.get()
        if item is None:
            break  # Stop signal
        location_id, image_path, class_label_detection = item
        _send_alert_via_api(location_id, image_path, class_label_detection)
        alert_queue.task_done()

def send_alert_via_api(location_id, image_path, class_label_detection):
    """
    Menambahkan data alert ke queue untuk diproses secara asynchronous.
    """
    alert_queue.put((location_id, image_path, class_label_detection))

def _send_alert_via_api(location_id, image_path, class_label_detection):
    """
    Fungsi internal untuk mengirimkan data alert ke API (dipanggil oleh worker thread).
    """
    try:
        # Determine the filename and MIME type based on how you saved the image
        if image_path.lower().endswith(('.jpg', '.jpeg')):
            filename = 'capture.jpeg'
            mime_type = 'image/jpeg'
        elif image_path.lower().endswith('.png'):
            filename = 'capture.png'
            mime_type = 'image/png'
        else:
            print(f"❌ Error: Format file gambar tidak didukung: {image_path}")
            return False

        with open(image_path, 'rb') as img_file:
            files = {'capture': (filename, img_file, mime_type)}
            data = {
                'location_id': location_id,
                'class_label_detection': class_label_detection
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"
            }

            response = requests.post(f"{API_BASE_URL}{ALERT_ENDPOINT}", headers=headers, data=data, files=files)
            response.raise_for_status()  # Raise an exception for bad status codes

            print(f"✅ Alert berhasil dikirim ke API (form data) untuk Lokasi ID: {location_id}")
            play_alarm_sound()  # Bunyi alarm ketika berhasil
            return True

    except FileNotFoundError:
        print(f"❌ Error: File gambar tidak ditemukan di path: {image_path}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Gagal mengirim alert ke API: {e}")
        if 'response' in locals() and response is not None:
            print(f"   Response status code: {response.status_code}")
            try:
                print(f"   Response body: {response.json()}")
            except json.JSONDecodeError:
                print(f"   Response body: {response.text}")
        return False

# Jalankan worker thread saat modul diimport
worker_thread = threading.Thread(target=alert_worker, daemon=True)
worker_thread.start()