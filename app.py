from flask import Flask, render_template, Response, redirect, url_for, jsonify, request, session
import cv2
import os
import threading
import json
from datetime import datetime
from pathlib import Path

# ── OCR import (graceful fallback jika belum install) ──────────────────────────
try:
    import pytesseract
    from PIL import Image
    import subprocess
    # Verifikasi tesseract binary tersedia
    subprocess.run(["tesseract", "--version"], capture_output=True, check=True)
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False
    print("[WARN] Tesseract belum terinstall.")
    print("       Jalankan: sudo apt install -y tesseract-ocr")
    print("                 pip install pytesseract pillow")

app = Flask(__name__)
app.secret_key = "dombaku-secret-2025"  # ganti dengan string random untuk produksi

# ── Direktori ──────────────────────────────────────────────────────────────────
CAPTURE_DIR = Path("captures")
HISTORY_FILE = Path("history.json")
CAPTURE_DIR.mkdir(exist_ok=True)

# ── State global (dilindungi lock) ────────────────────────────────────────────
frame_lock = threading.Lock()
latest_frame = None
camera = None
camera_lock = threading.Lock()


# ── Helper: history JSON ───────────────────────────────────────────────────────
def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []


def save_history(records):
    with open(HISTORY_FILE, "w") as f:
        json.dump(records, f, indent=2)


def append_history(record):
    records = load_history()
    records.insert(0, record)  # terbaru di atas
    records = records[:100]    # simpan max 100 entri
    save_history(records)


# ── Helper: inisialisasi kamera ───────────────────────────────────────────────
def init_camera():
    global camera
    with camera_lock:
        if camera is not None:
            camera.release()
        cam = cv2.VideoCapture(0, cv2.CAP_V4L2)
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if cam.isOpened():
            camera = cam
            return True
        return False


# ── Frame generator (MJPEG stream) ────────────────────────────────────────────
def generate_frames():
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

        ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + buffer.tobytes()
            + b"\r\n"
        )


# ── OCR: ekstrak ID ear tag dari gambar ───────────────────────────────────────
# ── OCR: ekstrak ID ear tag dari gambar ───────────────────────────────────────
def preprocess_for_ocr(image_path: str):
    """
    Preprocessing ringan untuk ear tag:
    - Grayscale
    - Resize 2x (Tesseract lebih suka gambar besar)
    - Denoise ringan
    - Contrast enhancement (CLAHE)
    """
    img = cv2.imread(image_path)
    if img is None:
        return None
 
    # Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
 
    # Resize 2x — Tesseract akurasi lebih baik pada gambar lebih besar
    h, w = gray.shape
    gray = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
 
    # Denoise ringan — hilangkan noise tanpa merusak tepi karakter
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)
 
    # CLAHE — tingkatkan kontras secara lokal, lebih lembut dari threshold
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
 
    # ── DEBUG: simpan hasil preprocessing agar bisa dicek ─────────────────
    debug_path = Path(image_path).parent / ("debug_" + Path(image_path).name)
    cv2.imwrite(str(debug_path), enhanced)
    print(f"[DEBUG] Preprocessed image saved → {debug_path}")
    # ──────────────────────────────────────────────────────────────────────
 
    return Image.fromarray(enhanced)


def run_ocr(image_path: str) -> str:
    """
    Jalankan OCR pada gambar menggunakan Tesseract.
    Dioptimasi untuk ear tag domba (angka/huruf pendek).
    """
    if not OCR_AVAILABLE:
        return "OCR_NOT_AVAILABLE"

    try:
        pil_img = preprocess_for_ocr(image_path)
        if pil_img is None:
            return "OCR_ERROR"

        # Config Tesseract:
        # --psm 8  = treat image as single word (cocok untuk ear tag)
        # --psm 7  = treat as single line (alternatif)
        # -c tessedit_char_whitelist = hanya baca angka & huruf kapital
        config = (
            "--psm 8 "
            "--oem 3 "
            "-c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        )

        raw = pytesseract.image_to_string(pil_img, config=config).strip()

        # Bersihkan: hapus spasi, newline, karakter aneh
        cleaned = "".join(c for c in raw if c.isalnum()).upper()

        # Filter panjang wajar ID ear tag (3–10 karakter)
        if 3 <= len(cleaned) <= 10:
            return cleaned
        elif cleaned:
            return cleaned  # kembalikan apa adanya jika di luar range
        else:
            return "TIDAK_TERBACA"

    except Exception as e:
        print(f"[OCR Error] {e}")
        return "OCR_ERROR"


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════

# ── Auth: Login ───────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def root():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # ── TODO: Ganti dengan validasi Firebase Auth ──────────────────────
        # Sementara hardcode untuk development/testing
        DEMO_EMAIL = "admin@dombaku.com"
        DEMO_PASSWORD = "dombaku123"

        if email == DEMO_EMAIL and password == DEMO_PASSWORD:
            session["logged_in"] = True
            session["user_name"] = email.split("@")[0].capitalize()
            session["user_email"] = email
            return redirect(url_for("dashboard"))
        else:
            error = "Email atau password salah."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("dashboard.html", user_name=session.get("user_name", "Peternak"))


# ── Halaman Kamera ────────────────────────────────────────────────────────────
@app.route("/kamera")
def kamera():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("kamera.html")


# ── Video feed (MJPEG) ────────────────────────────────────────────────────────
@app.route("/video_feed")
def video_feed():
    if not session.get("logged_in"):
        return "Unauthorized", 401
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# ── Capture + OCR (AJAX endpoint) ─────────────────────────────────────────────
@app.route("/api/capture", methods=["POST"])
def api_capture():
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    with frame_lock:
        frame = latest_frame.copy() if latest_frame is not None else None

    if frame is None:
        return jsonify({"success": False, "error": "Kamera belum siap."})

    # Simpan gambar
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.jpg"
    filepath = str(CAPTURE_DIR / filename)
    cv2.imwrite(filepath, frame)

    # Jalankan OCR
    ear_tag_id = run_ocr(filepath)

    # Simpan ke history
    record = {
        "id": timestamp,
        "filename": filename,
        "ear_tag_id": ear_tag_id,
        "timestamp": datetime.now().strftime("%d %b %Y, %H:%M:%S"),
        "ocr_available": OCR_AVAILABLE,
        # ── TODO: Tambahkan hasil AI rekomendasi kawin di sini ───────────
        "ai_result": None
    }
    append_history(record)

    return jsonify({
        "success": True,
        "filename": filename,
        "ear_tag_id": ear_tag_id,
        "timestamp": record["timestamp"],
        "ocr_available": OCR_AVAILABLE
    })


# ── Serve capture images ───────────────────────────────────────────────────────
@app.route("/captures/<filename>")
def serve_capture(filename):
    if not session.get("logged_in"):
        return "Unauthorized", 401
    from flask import send_from_directory
    return send_from_directory(str(CAPTURE_DIR), filename)


# ── Halaman Histori ───────────────────────────────────────────────────────────
@app.route("/histori")
def histori():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    records = load_history()
    return render_template("histori.html", records=records)


# ── API: ambil histori sebagai JSON (untuk dashboard stats) ───────────────────
@app.route("/histori_json")
def histori_json():
    if not session.get("logged_in"):
        return jsonify({"records": []})
    return jsonify({"records": load_history()})


# ── API: hapus satu record histori ────────────────────────────────────────────
@app.route("/api/history/<record_id>", methods=["DELETE"])
def delete_history(record_id):
    if not session.get("logged_in"):
        return jsonify({"success": False}), 401
    records = load_history()
    records = [r for r in records if r["id"] != record_id]
    save_history(records)
    return jsonify({"success": True})


# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 50)
    print("  DombaKu – Smart Sheep Breeding System")
    print("=" * 50)
    print(f"  OCR Status : {'✓ Tesseract siap' if OCR_AVAILABLE else '✗ Belum install (sudo apt install tesseract-ocr)'}")
    print(f"  Akses di   : http://localhost:5000")
    print(f"  Login demo : admin@dombaku.com / dombaku123")
    print("=" * 50)

    if not init_camera():
        print("[WARN] Kamera tidak terdeteksi di /dev/video0")

    app.run(host="0.0.0.0", port=5000, threaded=True)
