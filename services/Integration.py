import requests
import base64
import json
from ultralytics import YOLO

# Konfigurasi API
API_BASE_URL = "https://ppe-detection.azuhri-dev.com/api"  # Ganti dengan base URL API Anda
ALERT_ENDPOINT = "/violation"      # Ganti dengan endpoint API untuk mengirim alert

# Fungsi untuk mengirim alert via API
def send_alert_via_api(location_id, image_path):
    """
    Mengirimkan data alert (location_id dan capture_image sebagai form data) ke API.

    Args:
        location_id (int): ID lokasi tempat deteksi terjadi.
        image_path (str): Path ke file gambar hasil capture.

    Returns:
        bool: True jika pengiriman berhasil, False jika gagal.
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
            data = {'location_id': location_id}
            headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36"}

            response = requests.post(f"{API_BASE_URL}{ALERT_ENDPOINT}", headers=headers, data=data, files=files)
            response.raise_for_status()  # Raise an exception for bad status codes

            print(f"✅ Alert berhasil dikirim ke API (form data) untuk Lokasi ID: {location_id}")
            return True

    except FileNotFoundError:
        print(f"❌ Error: File gambar tidak ditemukan di path: {image_path}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Gagal mengirim alert ke API: {e}")
        if response is not None:
            print(f"   Response status code: {response.status_code}")
            try:
                print(f"   Response body: {response.json()}")
            except json.JSONDecodeError:
                print(f"   Response body: {response.text}")
        return False