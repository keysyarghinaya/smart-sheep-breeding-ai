import cv2
import platform
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

# Capture directory (shared)
CAPTURE_DIR = Path("captures")
CAPTURE_DIR.mkdir(exist_ok=True)

# Internal camera state
camera = None
camera_lock = threading.Lock()
frame_lock = threading.Lock()
latest_frame = None


def init_camera() -> bool:
    global camera
    with camera_lock:
        if camera is not None:
            try:
                camera.release()
            except Exception:
                pass

        # Auto-select backend based on OS
        if platform.system() == "Linux":
            cam = cv2.VideoCapture(0, cv2.CAP_V4L2)
        else:
            cam = cv2.VideoCapture(0)

        cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        try:
            cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass

        if cam.isOpened():
            camera = cam
            return True
        return False


def generate_frames():
    """MJPEG generator for Flask Response"""
    global latest_frame
    while True:
        with camera_lock:
            if camera is None or not camera.isOpened():
                break
            success, frame = camera.read()

        if not success:
            continue

        with frame_lock:
            latest_frame = frame.copy()

        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue

        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n'
            + buffer.tobytes()
            + b'\r\n'
        )


def get_latest_frame() -> Optional[object]:
    with frame_lock:
        if latest_frame is None:
            return None
        return latest_frame.copy()


def save_frame_temp(frame) -> str:
    """Save a frame temporarily for OCR and return path string."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_filename = f"{timestamp}.jpg"
    temp_filepath = str(CAPTURE_DIR / temp_filename)
    cv2.imwrite(temp_filepath, frame)
    return temp_filepath


def release_camera():
    global camera
    with camera_lock:
        try:
            if camera is not None:
                camera.release()
        except Exception:
            pass
        camera = None
