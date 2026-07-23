import re
from flask import Flask, render_template, Response, redirect, url_for, jsonify, request, session
from datetime import datetime

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from firestore_service import (
    get_sheep_by_eartag,
    get_candidate_sheep,
    get_user_by_email,
    add_marriage_record,
    get_marriage_history,
    delete_marriage_record,
)

from matching_service import get_top_matches

from camera_service import (
    CAPTURE_DIR,
    init_camera,
    generate_frames,
    get_latest_frame,
    save_frame_temp,
)
from camera_service import release_camera

from ocr_service import run_ocr, OCR_AVAILABLE

app = Flask(__name__)
app.secret_key = "dombaku-secret-2025"

TOP_MATCH_LIMIT = 5

def _rate_limit_handler(request_limit):
    return render_template("too_many_request.html"), 429

limiter = Limiter(
    key_func=get_remote_address,
    on_breach=_rate_limit_handler,
)
limiter.init_app(app)

# Inject user_name into all templates to fix 'Unknown' navbar issue
@app.context_processor
def inject_user():
    return {"user_name": session.get("user_name")}


# ═════════════════════════════════════════════════════════════════════════════=
#  ROUTES
# ═════════════════════════════════════════════════════════════════════════════=


@app.route("/", methods=["GET"])
def root():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(pattern, email):
            error = "Email tidak valid"
            return render_template("login.html", error=error)

        # Try Firestore users collection first
        user_doc = get_user_by_email(email)
        if user_doc:
            stored_pw = user_doc.get("password")
            status = user_doc.get("status", "").lower()
            if stored_pw:
                if password != stored_pw:
                    error = "Email atau password salah."
                else:
                    if status != "aktif":
                        error = "Akun tidak aktif."
                    else:
                        session["logged_in"] = True
                        session["user_name"] = user_doc.get("username") or email.split("@")[0].capitalize()
                        session["user_email"] = email
                        session["nama_peternak"] = user_doc.get("nama_peternak", session.get("user_name"))
                        session["role"] = user_doc.get("role")
                        session["is_paid"] = user_doc.get("is_paid", False)
                        return redirect(url_for("dashboard"))
            else:
                # Passwordless in users collection: accept if active
                if status != "aktif":
                    error = "Akun tidak aktif."
                else:
                    session["logged_in"] = True
                    session["user_name"] = user_doc.get("username") or email.split("@")[0].capitalize()
                    session["user_email"] = email
                    session["nama_peternak"] = user_doc.get("nama_peternak", session.get("user_name"))
                    session["role"] = user_doc.get("role")
                    session["is_paid"] = user_doc.get("is_paid", False)
                    return redirect(url_for("dashboard"))

        # Fallback demo credentials (local dev)
        DEMO_EMAIL = "admin@dombaku.com"
        DEMO_PASSWORD = "dombaku123"
        if email == DEMO_EMAIL and password == DEMO_PASSWORD:
            session["logged_in"] = True
            session["user_name"] = email.split("@")[0].capitalize()
            session["user_email"] = email
            session["nama_peternak"] = f"Peternakan {session.get('user_name')}"
            return redirect(url_for("dashboard"))

        if error is None:
            error = "Email atau password salah."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("dashboard.html", user_name=session.get("user_name", "Peternak"))


@app.route("/camera")
def camera_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    # Init camera only when page is opened
    try:
        if not init_camera():
            print("[WARN] Kamera tidak dapat diinisialisasi")
    except Exception:
        print("[WARN] init_camera failed")

    return render_template("camera.html")


@app.route("/video_feed")
def video_feed():
    if not session.get("logged_in"):
        return "Unauthorized", 401
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/api/capture", methods=["POST"])
def api_capture():
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    frame = get_latest_frame()
    if frame is None:
        return jsonify({"success": False, "error": "Kamera belum siap."})

    # Save temp for OCR
    temp_filepath = save_frame_temp(frame)
    ear_tag_id = run_ocr(temp_filepath)

    # cleanup temp files
    try:
        p = Path(temp_filepath)
        if p.exists():
            p.unlink()
        debug = p.parent / ("debug_" + p.name)
        if debug.exists():
            debug.unlink()
    except Exception as e:
        print(f"[WARN] Failed to cleanup temp files: {e}")

    return jsonify({
        "success": True,
        "filename": "",
        "ear_tag_id": ear_tag_id,
        "timestamp": datetime.now().strftime("%d %b %Y, %H:%M:%S"),
        "ocr_available": OCR_AVAILABLE,
    })


@app.route("/confirm", methods=["GET"])
def confirm():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    value = request.args.get("value", "")
    filename = request.args.get("file", "")
    # allow explicit warning passed in querystring (redirects)
    warning = request.args.get("warning", "")
    ocr_available = request.args.get("ocr_available", "True") in ("True", "true", "1")
    redirect_from = request.args.get("from", "")

    # Popup override from query param (set by confirm_save redirects)
    popup_param = request.args.get("popup", "")

    # If warning not provided explicitly, derive from OCR availability / value
    if not warning:
        if not ocr_available:
            warning = "Pembaca teks otomatis tidak tersedia pada server."
        elif value in ("OCR_NOT_AVAILABLE", "OCR_ERROR", "TIDAK_TERBACA"):
            value = ""
            # Trigger scan failed popup instead of inline warning
            if not popup_param:
                popup_param = "scanFailed"
        else:
            warning = ""

    return render_template("confirm.html", value=value, filename=filename, warning=warning, ocr_available=ocr_available, redirect_from=redirect_from, popup=popup_param)


@app.route("/confirm_save", methods=["POST"])
def confirm_save():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    ear_tag = request.form.get("ear_tag", "").strip()
    filename = request.form.get("filename", "")
    # Use nama_peternak from session
    nama_peternak = session.get("nama_peternak", f"Peternakan {session.get('user_name', '')}")

    if not ear_tag:
        return redirect(url_for("confirm", value="", file=filename, popup="emptyId"))

    sheep = get_sheep_by_eartag(ear_tag, nama_peternak)
    if sheep is None:
        return redirect(url_for("confirm", value=ear_tag, file=filename, popup="sheepNotFound"))

    opposite_gender = "Betina" if sheep.get("kelamin") == "Jantan" else "Jantan"
    candidates = get_candidate_sheep(opposite_gender, nama_peternak)

    if not candidates:
        return redirect(url_for("confirm", value=ear_tag, file=filename, popup="partnerNotFound"))

    ranked_matches = get_top_matches(sheep, candidates, nama_peternak, limit=TOP_MATCH_LIMIT)
    if not ranked_matches:
        return redirect(url_for("confirm", value=ear_tag, file=filename, warning="Tidak ada domba yang cocok (kemungkinan constraint lineage).", popup="matchingSheep"))

    session["current_sheep"] = sheep
    session["match_results"] = [
        {
            "candidate_eartag": str(match_result["candidate"].get("eartag")),
            "score": match_result["score"],
            "reason": match_result["reason"],
            "breakdown": match_result.get("breakdown", {}),
        }
        for match_result in ranked_matches
    ]
    session["match_result"] = session["match_results"][0]
    session["input_filename"] = filename

    return redirect(url_for("recommendation"))


@app.route("/recommendation", methods=["GET"])
def recommendation():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    sheep = session.get("current_sheep")
    match_results = session.get("match_results") or ([] if session.get("match_result") is None else [session.get("match_result")])

    if not sheep or not match_results:
        return redirect(url_for("confirm", warning="Session expired. Please rescan."))

    nama_peternak = session.get("nama_peternak", sheep.get("nama_peternak", ""))
    candidates = []

    for match_result in match_results:
        candidate_eartag = str(match_result["candidate_eartag"])
        candidate = get_sheep_by_eartag(candidate_eartag, nama_peternak)
        candidates.append({
            "candidate": candidate,
            "candidate_eartag": candidate_eartag,
            "score": int(match_result["score"]),
            "reason": match_result.get("reason", ""),
            "breakdown": match_result.get("breakdown", {}),
        })

    selected_candidate_eartag = candidates[0]["candidate_eartag"] if candidates else ""

    return render_template(
        "recommendation.html",
        sheep=sheep,
        candidates=candidates,
        selected_candidate_eartag=selected_candidate_eartag,
        top_match_count=len(candidates),
        input_filename=session.get("input_filename", ""),
    )


@app.route("/recommendation_confirm", methods=["POST"])
def recommendation_confirm():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    sheep = session.get("current_sheep")
    match_results = session.get("match_results") or ([] if session.get("match_result") is None else [session.get("match_result")])
    input_filename = session.get("input_filename", "")
    selected_candidate_eartag = request.form.get("candidate_eartag", "").strip()

    if not sheep or not match_results:
        return redirect(url_for("dashboard"))

    selected_match = None
    if selected_candidate_eartag:
        for match_result in match_results:
            if str(match_result.get("candidate_eartag")) == selected_candidate_eartag:
                selected_match = match_result
                break

    if selected_match is None:
        selected_match = match_results[0]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    record = {
        "filename": input_filename if input_filename else f"{timestamp}.jpg",
        "sheep_eartag": sheep.get("eartag"),
        "candidate_eartag": selected_match["candidate_eartag"],
        "match_score": selected_match["score"],
        "timestamp": datetime.now().strftime("%d %b %Y, %H:%M:%S"),
    }

    nama_peternak = session.get("nama_peternak", session.get("user_name", ""))
    add_marriage_record(record, nama_peternak)

    session.pop("current_sheep", None)
    session.pop("match_results", None)
    session.pop("match_result", None)
    session.pop("input_filename", None)

    return redirect(url_for("history"))


@app.route("/captures/<filename>")
def serve_capture(filename):
    if not session.get("logged_in"):
        return "Unauthorized", 401
    from flask import send_from_directory
    return send_from_directory(str(CAPTURE_DIR), filename)


@app.route("/history")
def history():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    nama_peternak = session.get("nama_peternak", session.get("user_name", ""))
    records = get_marriage_history(nama_peternak)
    return render_template("history.html", records=records)


@app.route("/history_json")
def history_json():
    if not session.get("logged_in"):
        return jsonify({"records": []})
    nama_peternak = session.get("nama_peternak", session.get("user_name", ""))
    return jsonify({"records": get_marriage_history(nama_peternak)})


@app.route('/camera_stop', methods=['POST'])
def camera_stop():
    """Endpoint to release camera when client page is unloaded/hidden."""
    if not session.get("logged_in"):
        return jsonify({"success": False}), 401
    try:
        release_camera()
    except Exception:
        pass
    return ('', 204)


@app.route('/api/sheep')
def api_sheep():
    if not session.get("logged_in"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    eartag = request.args.get('eartag') or request.args.get('value')
    if not eartag:
        return jsonify({"success": False, "error": "eartag missing"}), 400

    nama_peternak = session.get("nama_peternak", session.get("user_name", ""))
    sheep = get_sheep_by_eartag(eartag, nama_peternak)
    if not sheep:
        return jsonify({"success": False, "error": "not_found"}), 404

    return jsonify({"success": True, "sheep": sheep})


@app.route("/api/history/<record_id>", methods=["DELETE"])
def delete_history(record_id):
    if not session.get("logged_in"):
        return jsonify({"success": False}), 401
    success = delete_marriage_record(record_id)
    return jsonify({"success": success})


@app.route("/result")
def result_page():
    return render_template("result.html")


@app.route("/popup-test")
def popup_test():
    return render_template("popup_test.html")

@app.route("/loading")
def loading():
    return render_template("loading.html")

@app.route("/error-limit")
def error_limit():
    return render_template("error_limit.html")

@app.route("/error-general")
def error_general():
    return render_template("error_general.html")

@app.errorhandler(404)
def page_not_found(e):
    return render_template("not_found.html"), 404

@app.errorhandler(429)
def too_many_requests(e):
    return render_template("too_many_request.html"), 429

if __name__ == "__main__":
    print("=" * 50)
    print("  DombaKu – Smart Sheep Breeding System")
    print("=" * 50)
    print(f"  OCR Status : {'✓ Tesseract siap' if OCR_AVAILABLE else '✗ Belum install (sudo apt install tesseract-ocr)'}")
    print(f"  Akses di   : http://localhost:5000")
    print(f"  Login demo : admin@dombaku.com / dombaku123")
    print("=" * 50)
    print("  Kamera akan diinisialisasi saat halaman camera dibuka")
    print("=" * 50)

    app.run(host="0.0.0.0", port=5000, threaded=True, debug=True)