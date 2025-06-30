import sys
from services.Integration import send_alert_via_api, API_BASE_URL
import requests
from ultralytics import YOLO
import os
import cv2
import time
import threading

headers = {
    "User-Agent" : "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.103 Safari/537.36",
}

def load_model():
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(BASE_DIR, "models", "best.pt")
        model = YOLO(model_path)
        print(f"🧠 Model berhasil dimuat dari: {model_path}")
        return model, BASE_DIR
    except Exception as e:
        print(f"❌ Gagal memuat model dari {model_path}: {e}")
        sys.exit()

def fetch_model_config():
    try:
        print("ENDPOINT: ", API_BASE_URL)
        config_response = requests.get(f"{API_BASE_URL}/configuration-model", headers=headers)
        print(config_response)
        config_response.raise_for_status()
        config_data = config_response.json()
        if config_data and config_data.get("data") and len(config_data["data"]) > 0:
            threshold = float(config_data["data"][0]["threshold"])
            times_checking_perframe = int(config_data["data"][0]["times_checking_perframe"])
            print(f"⚙️ Konfigurasi model berhasil diambil dari API: Threshold={threshold}, Times Checking={times_checking_perframe}")
        else:
            print("⚠️ Konfigurasi model dari API tidak valid, menggunakan nilai default.")
            threshold = 0.5
            times_checking_perframe = 5
    except requests.exceptions.RequestException as e:
        print(f"❌ Gagal mengambil konfigurasi model dari API: {e}")
        threshold = 0.5
        times_checking_perframe = 5
    return threshold, times_checking_perframe

def fetch_video_sources(BASE_DIR):
    # ... (tidak berubah, kode sama seperti sebelumnya)
    video_sources = []
    try:
        print("ENDPOINT: ", API_BASE_URL)
        location_response = requests.get(f"{API_BASE_URL}/location", headers=headers)
        location_response.raise_for_status()
        location_data = location_response.json()
        print('Data location: ', location_data)
        if location_data and location_data.get("data"):
            if isinstance(location_data["data"], dict):
                data = location_data["data"]
                if data.get("data_source_type") == "video_file":
                    video_sources.append({
                        "location_id": data.get('id', 0),
                        "location": data.get("name", "Lokasi Tidak Diketahui"),
                        "file_path": os.path.join(BASE_DIR, "/", f"{data.get('content', '')}"),
                        "data_source_type": "video_file"
                    })
                elif data.get("data_source_type") == "rtsp_link":
                    video_sources.append({
                        "location_id": data.get('id', 0),
                        "location": data.get("name", "Lokasi Tidak Diketahui"),
                        "file_path": data.get("content", ""),
                        "data_source_type": "rtsp_link"
                    })
                elif data.get("data_source_type") == "camera":
                    video_sources.append({
                        "location_id": data.get('id', 0),
                        "location": data.get("name", "Lokasi Tidak Diketahui"),
                        "file_path": str(data.get("content", "0")),
                        "data_source_type": "camera"
                    })
            elif isinstance(location_data["data"], list):
                for location_info in location_data["data"]:
                    if location_info.get("data_source_type") == "video_file":
                        video_sources.append({
                            "location_id": location_info.get('id', 0),
                            "location": location_info.get("name", "Lokasi Tidak Diketahui"),
                            "file_path": f"{location_info.get('content', '')}",
                            "data_source_type": "video_file"
                        })
                    elif location_info.get("data_source_type") == "rtsp_link":
                        video_sources.append({
                            "location_id": location_info.get('id', 0),
                            "location": location_info.get("name", "Lokasi Tidak Diketahui"),
                            "file_path": location_info.get("content", ""),
                            "data_source_type": "rtsp_link"
                        })
                    elif location_info.get("data_source_type") == "camera":
                        video_sources.append({
                            "location_id": location_info.get('id', 0),
                            "location": location_info.get("name", "Lokasi Tidak Diketahui"),
                            "file_path": str(location_info.get("content", "0")),
                            "data_source_type": "camera"
                        })
            print(f"📍 Data lokasi (sumber video/rtsp/camera) berhasil diambil dari API: {video_sources}")
        else:
            print("⚠️ Data lokasi (sumber video/rtsp/camera) dari API tidak valid atau kosong.")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Gagal mengambil data lokasi (sumber video/rtsp/camera) dari API: {e}")

    return video_sources

def initialize_detection_dicts(video_sources, target_classes):
    email_sent_status = {}
    detection_counts = {}
    last_detection_frame = {}
    for source in video_sources:
        location = source["location"]
        email_sent_status[location] = {cls: False for cls in target_classes}
        detection_counts[location] = {cls: 0 for cls in target_classes}
        last_detection_frame[location] = {cls: None for cls in target_classes}
    return email_sent_status, detection_counts, last_detection_frame

def process_video_source_thread(source, model, threshold, times_checking_perframe, target_classes, detection_counts, last_detection_frame):
    # Bungkus process_video_source agar bisa dipanggil di thread
    try:
        process_video_source(
            source, model, threshold, times_checking_perframe,
            target_classes, detection_counts, last_detection_frame
        )
    except Exception as e:
        print(f"❌ Exception in thread for source {source.get('location', '')}: {e}")

def show_detection_window(window_name, frame, status=True):
    """
    Menampilkan frame hasil deteksi ke window OpenCV.
    """
    if status == True: 
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.imshow(window_name, frame)
        # Tekan 'q' untuk keluar dari window
        if cv2.waitKey(1) & 0xF == ord('q'):
            return False
    return True 

def process_video_source(source, model, threshold, times_checking_perframe, target_classes, detection_counts, last_detection_frame):
    location = source["location"]
    location_id = source.get("location_id", 0)
    file_path = source["file_path"]
    data_source_type = source.get("data_source_type", "")
    is_rtsp = file_path.startswith("rtsp://")
    is_mjpeg = data_source_type == "mjpeg" or (file_path.startswith("http") and "mjpg" in file_path.lower())
    is_camera = data_source_type == "camera" or (str(file_path).isdigit() and int(file_path) >= 0)

    window_name = f"Deteksi - {location}"

    if is_camera:
        camera_index = int(file_path)
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            print(f"❌ Tidak dapat membuka kamera dengan index {camera_index} untuk lokasi {location}")
            return
        print(f"🚀 Memproses kamera index {camera_index} untuk lokasi: {location}")
        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                print(f"⚠️ Tidak dapat membaca frame dari kamera {camera_index} ({location}). Selesai.")
                break

            frame_count += 1
            results = model(frame, verbose=False, conf=threshold)
            boxes = results[0].boxes
            detected_classes_in_frame = set()
            annotated_frame = results[0].plot()

            if boxes is None or boxes.cls is None or len(boxes.cls) == 0:
                print(f"[{location} - Frame {frame_count}] ❌ Tidak ada deteksi.")
                sys.stdout.flush()
                for cls in target_classes:
                    detection_counts[location][cls] = 0
                if not show_detection_window(window_name, frame):
                    break
                continue

            detected_labels = set()
            for box in boxes:
                cls_id = int(box.cls.item())
                conf = box.conf.item()
                class_name = model.names[cls_id]
                print(f"[{location} - Frame {frame_count}] ➤ Class terdeteksi: {class_name} (Confidence: {conf:.2f})")
                sys.stdout.flush()

                if class_name in target_classes:
                    detected_classes_in_frame.add(class_name)
                    detected_labels.add(class_name)
                    last_detection_frame[location][class_name] = annotated_frame

            for cls in target_classes:
                if cls in detected_classes_in_frame:
                    detection_counts[location][cls] += 1
                    print(f"[{location} - Frame {frame_count}] ⚠️ '{cls}' terdeteksi (hitungan: {detection_counts[location][cls]})")
                    sys.stdout.flush()
                else:
                    detection_counts[location][cls] = 0

                if detection_counts[location][cls] >= times_checking_perframe and last_detection_frame[location][cls] is not None:
                    alert_image_path = f"capture_{location.replace(' ', '_')}_{cls.replace(' ', '_')}.jpg"
                    cv2.imwrite(alert_image_path, last_detection_frame[location][cls])

                    detected_labels_str = ", ".join(sorted(detected_labels))
                    print(f"[{location} - Frame {frame_count}] 📧 Terdeteksi {times_checking_perframe} kali '{cls}'! Mengirim alert via API... Label terdeteksi: {detected_labels_str}")
                    detection_counts[location][cls] = 0
                    sys.stdout.flush()

                    send_alert_via_api(location_id, alert_image_path, detected_labels_str)

            if not show_detection_window(window_name, annotated_frame):
                break

        cap.release()
        cv2.destroyWindow(window_name)
        return

    if not (is_rtsp or is_mjpeg) and not os.path.exists(file_path):
        print(f"❌ File video tidak ditemukan: {file_path} untuk lokasi {location}")
        return

    max_retries = 5 if (is_rtsp or is_mjpeg) else 1
    retry_delay = 3  # detik

    for attempt in range(max_retries):
        if is_rtsp:
            cap = cv2.VideoCapture(file_path, cv2.CAP_FFMPEG)
        elif is_mjpeg:
            cap = cv2.VideoCapture(file_path)
        else:
            cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            print(f"❌ Gagal membuka {'RTSP stream' if is_rtsp else ('MJPEG stream' if is_mjpeg else 'video')} dari: {location} ({file_path}), percobaan ke-{attempt+1}")
            cap.release()
            if is_rtsp or is_mjpeg:
                time.sleep(retry_delay)
                continue
            else:
                return
        print(f"🚀 Memproses {'RTSP stream' if is_rtsp else ('MJPEG stream' if is_mjpeg else 'video')} dari: {location} ({file_path})")
        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                print(f"⚠️ Tidak dapat membaca frame dari {location}.", end=' ')
                if is_rtsp or is_mjpeg:
                    print("Mencoba reconnect...")
                    cap.release()
                    time.sleep(retry_delay)
                    break
                else:
                    print("Selesai memproses video.")
                    break

            frame_count += 1
            results = model(frame, verbose=False, conf=threshold)
            boxes = results[0].boxes
            detected_classes_in_frame = set()
            annotated_frame = results[0].plot()

            if boxes is None or boxes.cls is None or len(boxes.cls) == 0:
                print(f"[{location} - Frame {frame_count}] ❌ Tidak ada deteksi.")
                sys.stdout.flush()
                for cls in target_classes:
                    detection_counts[location][cls] = 0
                if not show_detection_window(window_name, frame):
                    break
                continue

            detected_labels = set()
            for box in boxes:
                cls_id = int(box.cls.item())
                conf = box.conf.item()
                class_name = model.names[cls_id]
                print(f"[{location} - Frame {frame_count}] ➤ Class terdeteksi: {class_name} (Confidence: {conf:.2f})")
                sys.stdout.flush()

                if class_name in target_classes:
                    detected_classes_in_frame.add(class_name)
                    detected_labels.add(class_name)
                    last_detection_frame[location][class_name] = annotated_frame

            for cls in target_classes:
                if cls in detected_classes_in_frame:
                    detection_counts[location][cls] += 1
                    print(f"[{location} - Frame {frame_count}] ⚠️ '{cls}' terdeteksi (hitungan: {detection_counts[location][cls]})")
                    sys.stdout.flush()
                else:
                    detection_counts[location][cls] = 0

                if detection_counts[location][cls] >= times_checking_perframe and last_detection_frame[location][cls] is not None:
                    alert_image_path = f"capture_{location.replace(' ', '_')}_{cls.replace(' ', '_')}.jpg"
                    cv2.imwrite(alert_image_path, last_detection_frame[location][cls])

                    detected_labels_str = ", ".join(sorted(detected_labels))
                    print(f"[{location} - Frame {frame_count}] 📧 Terdeteksi {times_checking_perframe} kali '{cls}'! Mengirim alert via API... Label terdeteksi: {detected_labels_str}")
                    detection_counts[location][cls] = 0
                    sys.stdout.flush()

                    send_alert_via_api(location_id, alert_image_path, detected_labels_str)

            if not show_detection_window(window_name, annotated_frame):
                break

        cap.release()
        cv2.destroyWindow(window_name)
        if not (is_rtsp or is_mjpeg):
            break

def detectionWithSources():
    model, BASE_DIR = load_model()
    threshold, times_checking_perframe = fetch_model_config()
    video_sources = fetch_video_sources(BASE_DIR)
    target_classes = ["unhelmet", "no wear vest", "no wear safetyboot"]
    print(video_sources)
    email_sent_status, detection_counts, last_detection_frame = initialize_detection_dicts(video_sources, target_classes)

    # threads = []
    # for source in video_sources:
    #     t = threading.Thread(
    #         target=process_video_source_thread,
    #         args=(source, model, threshold, times_checking_perframe, target_classes, detection_counts, last_detection_frame)
    #     )
    #     t.daemon = True
    #     t.start()
    #     threads.append(t)

    # for t in threads:
    #     t.join()
    for source in video_sources:
        process_video_source_thread(
            source, model, threshold, times_checking_perframe, target_classes, detection_counts, last_detection_frame
        )

    print("✅ Selesai memproses semua video.")

def detectionWithCamera(camera_index=0):
    # ... (tidak berubah, kode sama seperti sebelumnya)
    model, BASE_DIR = load_model()
    threshold, times_checking_perframe = fetch_model_config()
    target_classes = ["unhelmet", "no wear vest", "no wear safetyboot"]
    detection_counts = {cls: 0 for cls in target_classes}
    last_detection_frame = {cls: None for cls in target_classes}

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"❌ Tidak dapat membuka kamera dengan index {camera_index}")
        return

    print(f"🚀 Memulai deteksi dengan kamera index {camera_index}")
    frame_count = 0
    window_name = "Deteksi Kamera"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Tidak dapat membaca frame dari kamera.")
            break

        frame_count += 1
        results = model(frame, verbose=False, conf=threshold)
        boxes = results[0].boxes
        detected_classes_in_frame = set()

        if boxes is None or boxes.cls is None or len(boxes.cls) == 0:
            print(f"[Kamera - Frame {frame_count}] ❌ Tidak ada deteksi.")
            sys.stdout.flush()
            for cls in target_classes:
                detection_counts[cls] = 0
            cv2.imshow(window_name, frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            continue

        print(f"[Kamera - Frame {frame_count}] ✅ Jumlah box terdeteksi: {len(boxes.cls)}")
        sys.stdout.flush()

        annotated_frame = results[0].plot()

        for i, box in enumerate(boxes):
            cls_id = int(box.cls.item())
            conf = box.conf.item()
            class_name = model.names[cls_id]
            print(f"[Kamera - Frame {frame_count}] ➤ Class terdeteksi: {class_name} (Confidence: {conf:.2f})")
            sys.stdout.flush()

            if class_name in target_classes:
                detected_classes_in_frame.add(class_name)
                last_detection_frame[class_name] = annotated_frame

        for cls in target_classes:
            if cls in detected_classes_in_frame:
                detection_counts[cls] += 1
                print(f"[Kamera - Frame {frame_count}] ⚠️ '{cls}' terdeteksi (hitungan: {detection_counts[cls]})")
                sys.stdout.flush()
            else:
                detection_counts[cls] = 0

            if detection_counts[cls] >= times_checking_perframe and last_detection_frame[cls] is not None:
                alert_image_path = f"capture_camera_{cls.replace(' ', '_')}.jpg"
                cv2.imwrite(alert_image_path, last_detection_frame[cls])

                print(f"[Kamera - Frame {frame_count}] 📧 Terdeteksi {times_checking_perframe} kali '{cls}'! (Kamera)")
                detection_counts[cls] = 0
                sys.stdout.flush()
                # Jika ingin mengirim alert via API, tambahkan di sini

        cv2.imshow(window_name, annotated_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyWindow(window_name)
    print("✅ Selesai deteksi kamera.")

if __name__ == "__main__":
    detectionWithSources()
    # detectionWithCamera(camera_index=0)  # Ganti dengan index kamera yang sesuai