from flask import render_template, request, jsonify
import sqlite3, datetime, base64
import numpy as np
import cv2

from helpers import (
    get_db,
    enhance_lighting_bgr,
    face_cascade,
    _get_cached_students,
    _perf_now,
    _build_perf,
    FACE_DETECT_SCALE,
    FACE_MIN_SIZE,
    RECOG_THRESHOLD
)

from models.facenet_model import get_face_embedding


def register_kiosk_routes(app):

    # ================= SETUP =================
    @app.route("/kiosk/setup")
    def kiosk_setup():
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT DISTINCT room_name FROM sessions")
        rooms = [r["room_name"] for r in cur.fetchall()]

        conn.close()
        return render_template("kiosk/kiosk_setup.html", rooms=rooms)

    # ================= CAMERA =================
    @app.route("/kiosk/camera")
    def kiosk_camera():
        return render_template("kiosk/kiosk_camera.html")

    # ================= CAPTURE =================
    @app.route("/kiosk/capture", methods=["POST"])
    def kiosk_capture():
        data = request.json
        image_data = data.get("image")
        session_id = data.get("session_id")

        img_bytes = base64.b64decode(image_data.split(",")[1])
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)

        img = enhance_lighting_bgr(img)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.2, 5)

        if len(faces) == 0:
            return jsonify({"recognized": False})

        x, y, w, h = faces[0]
        face = cv2.resize(img[y:y+h, x:x+w], (160, 160))
        emb = get_face_embedding(face)

        ids, embs = _get_cached_students()
        dists = np.linalg.norm(embs - emb, axis=1)
        idx = np.argmin(dists)

        if dists[idx] > RECOG_THRESHOLD:
            return jsonify({"recognized": False})

        uid = ids[idx]

        conn = get_db()
        cur = conn.cursor()

        now = datetime.datetime.now()

        cur.execute("""
            INSERT INTO attendance (session_id, university_id, check_in, status)
            VALUES (?, ?, ?, 'Present')
        """, (session_id, uid, now))

        conn.commit()
        conn.close()

        return jsonify({"recognized": True})