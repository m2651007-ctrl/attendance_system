from flask import render_template, request, redirect, session, jsonify
import hashlib, datetime, base64
import numpy as np
import cv2

from helpers import (
    get_db,
    _get_session_row,
    enhance_lighting_bgr,
    face_cascade,
    _get_cached_students,
    RECOG_THRESHOLD
)

from models.facenet_model import get_face_embedding


def register_doctor_routes(app):

    # ===================== LOGIN =====================
    @app.route("/doctor/login", methods=["GET", "POST"])
    def doctor_login():
        if request.method == "POST":
            username = request.form.get("username")
            password = request.form.get("password")

            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM doctors WHERE username=?", (username,))
            d = cur.fetchone()
            conn.close()

            if d and hashlib.sha256(password.encode()).hexdigest() == d["password_hash"]:
                session["doctor_id"] = d["doctor_id"]
                session["doctor_name"] = d["name"]
                return redirect("/doctor/dashboard")

            return "خطأ في تسجيل الدخول"

        return render_template("doctor/login.html")


    # ===================== DASHBOARD =====================
    @app.route("/doctor/dashboard")
    def doctor_dashboard():
        if "doctor_id" not in session:
            return redirect("/doctor/login")

        return render_template("doctor/doctor_dashboard.html", doctor_name=session["doctor_name"])


    # ===================== COURSES =====================
    @app.route("/doctor/courses")
    def doctor_courses():
        if "doctor_id" not in session:
            return redirect("/doctor/login")

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT session_id, course_name,
                   COALESCE(session_number,'') AS session_number
            FROM sessions
            WHERE doctor_id=?
        """, (session["doctor_id"],))

        sessions = cur.fetchall()
        conn.close()

        return render_template("doctor/doctor_courses.html", sessions=sessions)


    # ===================== ATTENDANCE =====================
    @app.route("/doctor/attendance")
    def doctor_attendance():
        if "doctor_id" not in session:
            return redirect("/doctor/login")

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT session_id, course_name,
                   COALESCE(session_number,'') AS session_number
            FROM sessions
            WHERE doctor_id=?
        """, (session["doctor_id"],))

        sessions = cur.fetchall()
        conn.close()

        return render_template("doctor/doctor_attendance.html", sessions=sessions)


    # ===================== FACE CHECK-IN =====================
    @app.route("/doctor/attendance/capture", methods=["POST"])
    def capture():
        if "doctor_id" not in session:
            return jsonify({"ok": False})

        data = request.json
        image_data = data["image"]
        session_id = data["session_id"]

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
        best = np.argmin(dists)

        if dists[best] > RECOG_THRESHOLD:
            return jsonify({"recognized": False})

        uid = ids[best]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO attendance (session_id, university_id, check_in, status)
            VALUES (?, ?, ?, 'Present')
        """, (session_id, uid, datetime.datetime.now()))

        conn.commit()
        conn.close()

        return jsonify({"recognized": True})


    # ===================== CHECKOUT PAGE (🔥 هذا كان ناقص) =====================
    @app.route("/doctor/attendance/checkout_page")
    def checkout_page():
        if "doctor_id" not in session:
            return redirect("/doctor/login")

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT session_id, course_name,
                   COALESCE(session_number,'') AS session_number
            FROM sessions
            WHERE doctor_id=?
        """, (session["doctor_id"],))

        sessions = cur.fetchall()
        conn.close()

        return render_template("doctor/doctor_checkout.html", sessions=sessions)


    # ===================== CHECKOUT ACTION =====================
    @app.route("/doctor/attendance/checkout/capture", methods=["POST"])
    def checkout():
        if "doctor_id" not in session:
            return jsonify({"ok": False})

        data = request.json
        session_id = data["session_id"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            UPDATE attendance
            SET check_out=?
            WHERE session_id=?
        """, (datetime.datetime.now(), session_id))

        conn.commit()
        conn.close()

        return jsonify({"ok": True})


    # ===================== LOGOUT =====================
    @app.route("/doctor/logout")
    def logout():
        session.clear()
        return redirect("/doctor/login")