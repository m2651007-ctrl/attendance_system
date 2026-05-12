from flask import render_template, request, redirect, session, jsonify
import hashlib, datetime, base64
import numpy as np
import cv2

from helpers import (
    get_db,
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
                session["doctor_id"]   = d["doctor_id"]
                session["doctor_name"] = d["name"]
                return redirect("/doctor/dashboard")

            return render_template("doctor/login.html", error="اسم المستخدم أو كلمة المرور غير صحيحة")

        return render_template("doctor/login.html", error=None)


    # ===================== DASHBOARD =====================
    @app.route("/doctor/dashboard")
    def doctor_dashboard():
        if "doctor_id" not in session:
            return redirect("/doctor/login")

        conn = get_db()
        cur  = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM sessions WHERE doctor_id=?", (session["doctor_id"],))
        total_sessions = cur.fetchone()[0]

        today = datetime.date.today().isoformat()
        cur.execute("""
            SELECT COUNT(*) FROM attendance a
            JOIN sessions s ON a.session_id = s.session_id
            WHERE s.doctor_id=? AND DATE(a.check_in)=? AND a.status='Present'
        """, (session["doctor_id"], today))
        today_present = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM attendance a
            JOIN sessions s ON a.session_id = s.session_id
            WHERE s.doctor_id=?
        """, (session["doctor_id"],))
        total_attendance = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT a.university_id,
                    ROUND(SUM(CASE WHEN a.status='Absent' THEN 1.0 ELSE 0 END) / COUNT(*) * 100, 1) AS pct
                FROM attendance a
                JOIN sessions s ON a.session_id = s.session_id
                WHERE s.doctor_id=?
                GROUP BY a.university_id
                HAVING pct > 25
            )
        """, (session["doctor_id"],))
        total_deprived = cur.fetchone()[0]

        conn.close()

        return render_template("doctor/doctor_dashboard.html",
            doctor_name      = session["doctor_name"],
            total_sessions   = total_sessions,
            total_attendance = total_attendance,
            total_deprived   = total_deprived,
            today_present    = today_present
        )


    # ===================== COURSES =====================
    @app.route("/doctor/courses")
    def doctor_courses():
        if "doctor_id" not in session:
            return redirect("/doctor/login")

        conn = get_db()
        cur  = conn.cursor()

        cur.execute("""
            SELECT session_id,
                   course_name,
                   COALESCE(session_number, '')  AS session_number,
                   COALESCE(days, '')             AS schedule_days,
                   COALESCE(start_time, '') || ' - ' || COALESCE(end_time, '') AS schedule_time,
                   COALESCE(room_name, '')        AS room_name,
                   COALESCE(room_code, '')        AS room_code,
                   COALESCE(capacity, 0)          AS capacity
            FROM sessions
            WHERE doctor_id=?
            ORDER BY course_name
        """, (session["doctor_id"],))

        sessions_list = cur.fetchall()
        conn.close()

        return render_template("doctor/doctor_courses.html", sessions=sessions_list)


    # ===================== ATTENDANCE PAGE =====================
    @app.route("/doctor/attendance")
    def doctor_attendance():
        if "doctor_id" not in session:
            return redirect("/doctor/login")

        conn = get_db()
        cur  = conn.cursor()

        cur.execute("""
            SELECT session_id,
                   course_name,
                   COALESCE(session_number, '')  AS session_number,
                   COALESCE(days, '')             AS schedule_days,
                   COALESCE(start_time, '') || ' - ' || COALESCE(end_time, '') AS schedule_time,
                   COALESCE(room_name, '')        AS room_name
            FROM sessions
            WHERE doctor_id=?
            ORDER BY course_name
        """, (session["doctor_id"],))

        sessions_list = cur.fetchall()
        conn.close()

        return render_template("doctor/doctor_attendance.html", sessions=sessions_list)


    # ===================== FACE CHECK-IN =====================
    @app.route("/doctor/attendance/capture", methods=["POST"])
    def capture():
        if "doctor_id" not in session:
            return jsonify({"ok": False})

        data       = request.json
        image_data = data["image"]
        session_id = data["session_id"]

        img_bytes = base64.b64decode(image_data.split(",")[1])
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        img = enhance_lighting_bgr(img)

        gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.2, 5)

        if len(faces) == 0:
            return jsonify({"recognized": False})

        x, y, w, h = faces[0]
        face = cv2.resize(img[y:y+h, x:x+w], (160, 160))
        emb  = get_face_embedding(face)

        ids, embs = _get_cached_students()
        dists = np.linalg.norm(embs - emb, axis=1)
        best  = int(np.argmin(dists))

        if dists[best] > RECOG_THRESHOLD:
            return jsonify({"recognized": False, "box": [int(x), int(y), int(w), int(h)]})

        uid = ids[best]

        conn = get_db()
        cur  = conn.cursor()
        cur.execute("SELECT name, academic_number FROM students WHERE university_id=?", (uid,))
        student = cur.fetchone()

        today = datetime.date.today().isoformat()
        cur.execute("""
            SELECT id FROM attendance
            WHERE session_id=? AND university_id=? AND DATE(check_in)=?
        """, (session_id, uid, today))
        existing = cur.fetchone()

        new_record = False
        if not existing:
            # تحديد حاضر أو متأخر
            cur.execute("SELECT start_time FROM sessions WHERE session_id=?", (session_id,))
            s_row = cur.fetchone()
            status = "Present"
            if s_row and s_row["start_time"]:
                try:
                    now = datetime.datetime.now()
                    h_, m_ = map(int, s_row["start_time"].split(":"))
                    start_dt = now.replace(hour=h_, minute=m_, second=0, microsecond=0)
                    if (now - start_dt).total_seconds() / 60 > 15:
                        status = "Late"
                except Exception:
                    pass

            cur.execute("""
                INSERT INTO attendance (session_id, university_id, check_in, status)
                VALUES (?, ?, ?, ?)
            """, (session_id, uid, datetime.datetime.now(), status))
            conn.commit()
            new_record = True

        conn.close()

        return jsonify({
            "recognized": True,
            "new_record":  new_record,
            "box":         [int(x), int(y), int(w), int(h)],
            "student": {
                "university_id":   uid,
                "name":            student["name"]            if student else uid,
                "academic_number": student["academic_number"] if student else ""
            }
        })


    # ===================== ATTENDANCE LIST =====================
    @app.route("/doctor/attendance/list")
    def attendance_list():
        if "doctor_id" not in session:
            return jsonify({"ok": False})

        session_id = request.args.get("session_id")
        if not session_id:
            return jsonify({"ok": False})

        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT a.id, s.name, s.academic_number, a.university_id,
                   a.check_in, a.check_out, a.status
            FROM attendance a
            LEFT JOIN students s ON a.university_id = s.university_id
            WHERE a.session_id=?
            ORDER BY a.check_in DESC
        """, (session_id,))

        rows = [dict(
            id              = r["id"],
            name            = r["name"] or r["university_id"],
            academic_number = r["academic_number"] or "",
            university_id   = r["university_id"],
            check_in        = r["check_in"]  or "",
            check_out       = r["check_out"] or "",
            status          = r["status"]
        ) for r in cur.fetchall()]

        conn.close()
        return jsonify({"ok": True, "rows": rows})


    # ===================== MANUAL ATTENDANCE =====================
    @app.route("/doctor/attendance/manual", methods=["POST"])
    def manual_attendance():
        if "doctor_id" not in session:
            return jsonify({"ok": False, "msg": "غير مصرح"})

        data          = request.json
        session_id    = data.get("session_id")
        university_id = data.get("university_id", "").strip()
        status        = data.get("status", "Present")

        if not session_id or not university_id:
            return jsonify({"ok": False, "msg": "بيانات ناقصة"})

        conn = get_db()
        cur  = conn.cursor()

        cur.execute("SELECT doctor_id FROM sessions WHERE session_id=?", (session_id,))
        s_row = cur.fetchone()
        if not s_row or s_row["doctor_id"] != session["doctor_id"]:
            conn.close()
            return jsonify({"ok": False, "msg": "غير مصرح"})

        cur.execute("SELECT name, academic_number FROM students WHERE university_id=?", (university_id,))
        student = cur.fetchone()
        if not student:
            conn.close()
            return jsonify({"ok": False, "msg": "الطالب غير موجود"})

        today = datetime.date.today().isoformat()
        cur.execute("""
            SELECT id FROM attendance
            WHERE session_id=? AND university_id=? AND DATE(check_in)=?
        """, (session_id, university_id, today))
        existing = cur.fetchone()

        if existing:
            cur.execute("""
                UPDATE attendance SET status=?
                WHERE session_id=? AND university_id=? AND DATE(check_in)=?
            """, (status, session_id, university_id, today))
        else:
            cur.execute("""
                INSERT INTO attendance (session_id, university_id, check_in, status)
                VALUES (?, ?, ?, ?)
            """, (session_id, university_id, datetime.datetime.now(), status))

        conn.commit()
        conn.close()

        return jsonify({"ok": True, "student": {
            "name":            student["name"],
            "academic_number": student["academic_number"],
            "university_id":   university_id,
            "status":          status
        }})


    # ===================== STATS + ANALYTICS =====================
    @app.route("/doctor/attendance/stats")
    def attendance_stats():
        if "doctor_id" not in session:
            return jsonify({"ok": False})

        session_id = request.args.get("session_id")
        if not session_id:
            return jsonify({"ok": False})

        conn  = get_db()
        cur   = conn.cursor()
        today = datetime.date.today().isoformat()

        cur.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE session_id=? AND DATE(check_in)=? AND status='Present'
        """, (session_id, today))
        present_today = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM attendance
            WHERE session_id=? AND DATE(check_in)=? AND status='Absent'
        """, (session_id, today))
        absent_today = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as total_present,
                   SUM(CASE WHEN status='Absent'  THEN 1 ELSE 0 END) as total_absent
            FROM attendance WHERE session_id=?
        """, (session_id,))
        r = cur.fetchone()
        total_all     = r["total"]         or 1
        total_present = r["total_present"] or 0
        total_absent  = r["total_absent"]  or 0

        cur.execute("""
            SELECT COUNT(*) FROM (
                SELECT university_id,
                    ROUND(SUM(CASE WHEN status='Absent' THEN 1.0 ELSE 0 END) / COUNT(*) * 100, 1) AS pct
                FROM attendance WHERE session_id=?
                GROUP BY university_id HAVING pct > 25
            )
        """, (session_id,))
        deprived = cur.fetchone()[0]

        cur.execute("""
            SELECT DATE(check_in) as day,
                   SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) as present,
                   SUM(CASE WHEN status='Absent'  THEN 1 ELSE 0 END) as absent
            FROM attendance WHERE session_id=?
            GROUP BY day ORDER BY day DESC LIMIT 10
        """, (session_id,))
        trend = [{"day": r["day"], "present": r["present"], "absent": r["absent"]}
                 for r in cur.fetchall()]

        cur.execute("""
            SELECT
                SUM(CASE WHEN pct >= 75 THEN 1 ELSE 0 END) as excellent,
                SUM(CASE WHEN pct >= 50 AND pct < 75 THEN 1 ELSE 0 END) as warning,
                SUM(CASE WHEN pct < 50 THEN 1 ELSE 0 END) as critical
            FROM (
                SELECT university_id,
                    ROUND(SUM(CASE WHEN status='Present' THEN 1.0 ELSE 0 END) / COUNT(*) * 100, 1) AS pct
                FROM attendance WHERE session_id=?
                GROUP BY university_id
            )
        """, (session_id,))
        dist = cur.fetchone()

        conn.close()

        return jsonify({
            "ok":            True,
            "present_today": present_today,
            "absent_today":  absent_today,
            "deprived":      deprived,
            "total_present": total_present,
            "total_absent":  total_absent,
            "present_pct":   round(total_present / total_all * 100, 1),
            "absent_pct":    round(total_absent  / total_all * 100, 1),
            "trend":         list(reversed(trend)),
            "dist": {
                "excellent": dist["excellent"] or 0,
                "warning":   dist["warning"]   or 0,
                "critical":  dist["critical"]  or 0
            }
        })


    # ===================== DEPRIVED LIST =====================
    @app.route("/doctor/attendance/deprived")
    def deprived_students():
        if "doctor_id" not in session:
            return jsonify({"ok": False})

        session_id = request.args.get("session_id")
        if not session_id:
            return jsonify({"ok": False})

        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT s.name, s.academic_number, a.university_id,
                   COUNT(*) as total_lectures,
                   SUM(CASE WHEN a.status='Absent' THEN 1 ELSE 0 END) as absent_count,
                   ROUND(SUM(CASE WHEN a.status='Absent' THEN 1.0 ELSE 0 END) / COUNT(*) * 100, 1) as absence_pct
            FROM attendance a
            LEFT JOIN students s ON a.university_id = s.university_id
            WHERE a.session_id=?
            GROUP BY a.university_id
            HAVING absence_pct > 25
            ORDER BY absence_pct DESC
        """, (session_id,))

        rows = [dict(
            name            = r["name"] or r["university_id"],
            academic_number = r["academic_number"] or "",
            university_id   = r["university_id"],
            total_lectures  = r["total_lectures"],
            absent_count    = r["absent_count"],
            absence_pct     = r["absence_pct"]
        ) for r in cur.fetchall()]

        conn.close()
        return jsonify({"ok": True, "rows": rows})


    # ===================== EXPORT CSV =====================
    @app.route("/doctor/attendance/export")
    def export_attendance():
        if "doctor_id" not in session:
            return redirect("/doctor/login")

        session_id = request.args.get("session_id")
        if not session_id:
            return "يرجى تحديد المحاضرة", 400

        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT a.id, s.name, s.academic_number, a.university_id,
                   a.check_in, a.check_out, a.status
            FROM attendance a
            LEFT JOIN students s ON a.university_id = s.university_id
            WHERE a.session_id=? ORDER BY a.check_in
        """, (session_id,))
        rows = cur.fetchall()

        cur.execute("SELECT course_name FROM sessions WHERE session_id=?", (session_id,))
        course = cur.fetchone()
        conn.close()

        import csv, io
        from flask import Response

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["الاسم","الرقم الأكاديمي","الرقم الجامعي","وقت الدخول","وقت الانصراف","الحالة"])
        for r in rows:
            writer.writerow([
                r["name"] or r["university_id"],
                r["academic_number"] or "",
                r["university_id"],
                r["check_in"]  or "",
                r["check_out"] or "",
                r["status"]
            ])

        course_name = course["course_name"] if course else "attendance"
        filename    = f"attendance_{course_name}_{datetime.date.today()}.csv"

        return Response(
            "\ufeff" + output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )


    # ===================== CHECKOUT PAGE =====================
    @app.route("/doctor/attendance/checkout_page")
    def checkout_page():
        if "doctor_id" not in session:
            return redirect("/doctor/login")

        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT session_id,
                   course_name,
                   COALESCE(session_number, '') AS session_number,
                   COALESCE(room_name, '')      AS room_name
            FROM sessions
            WHERE doctor_id=?
            ORDER BY course_name
        """, (session["doctor_id"],))
        sessions_list = cur.fetchall()
        conn.close()

        return render_template("doctor/doctor_checkout.html", sessions=sessions_list)


    # ===================== CHECKOUT CAPTURE =====================
    @app.route("/doctor/attendance/checkout/capture", methods=["POST"])
    def checkout():
        if "doctor_id" not in session:
            return jsonify({"ok": False})

        data       = request.json
        image_data = data["image"]
        session_id = data["session_id"]

        img_bytes = base64.b64decode(image_data.split(",")[1])
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        img = enhance_lighting_bgr(img)

        gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.2, 5)

        if len(faces) == 0:
            return jsonify({"recognized": False})

        x, y, w, h = faces[0]
        face = cv2.resize(img[y:y+h, x:x+w], (160, 160))
        emb  = get_face_embedding(face)

        ids, embs = _get_cached_students()
        dists = np.linalg.norm(embs - emb, axis=1)
        best  = int(np.argmin(dists))

        if dists[best] > RECOG_THRESHOLD:
            return jsonify({"recognized": False, "box": [int(x), int(y), int(w), int(h)]})

        uid = ids[best]
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("SELECT name, academic_number FROM students WHERE university_id=?", (uid,))
        student = cur.fetchone()

        today = datetime.date.today().isoformat()
        cur.execute("""
            SELECT id FROM attendance
            WHERE session_id=? AND university_id=? AND DATE(check_in)=? AND check_out IS NULL
        """, (session_id, uid, today))
        existing = cur.fetchone()

        checked_out = False
        if existing:
            cur.execute(
                "UPDATE attendance SET check_out=? WHERE id=?",
                (datetime.datetime.now(), existing["id"])
            )
            conn.commit()
            checked_out = True

        conn.close()

        return jsonify({
            "recognized":  True,
            "checked_out": checked_out,
            "box":         [int(x), int(y), int(w), int(h)],
            "student": {
                "university_id":   uid,
                "name":            student["name"]            if student else uid,
                "academic_number": student["academic_number"] if student else ""
            }
        })


    # ===================== CHECKOUT LIST =====================
    @app.route("/doctor/attendance/checkout/list")
    def checkout_list():
        if "doctor_id" not in session:
            return jsonify({"ok": False})

        session_id = request.args.get("session_id")
        if not session_id:
            return jsonify({"ok": False})

        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT a.id, s.name, s.academic_number, a.university_id,
                   a.check_in, a.check_out, a.status
            FROM attendance a
            LEFT JOIN students s ON a.university_id = s.university_id
            WHERE a.session_id=? ORDER BY a.check_in DESC
        """, (session_id,))

        rows = [dict(
            id              = r["id"],
            name            = r["name"] or r["university_id"],
            academic_number = r["academic_number"] or "",
            university_id   = r["university_id"],
            check_in        = r["check_in"]  or "",
            check_out       = r["check_out"] or "—",
            status          = r["status"]
        ) for r in cur.fetchall()]

        conn.close()
        return jsonify({"ok": True, "rows": rows})


    # ===================== LOGOUT =====================
    @app.route("/doctor/logout")
    def logout():
        session.clear()
        return redirect("/doctor/login")


    # ===================== REPORT STATUS =====================
    @app.route("/doctor/attendance/report_status", methods=["POST"])
    def report_status():
        if "doctor_id" not in session:
            return jsonify({"ok": False, "msg": "غير مصرح"})

        data          = request.json
        session_id    = data.get("session_id")
        university_id = data.get("university_id", "").strip()
        student_name  = data.get("student_name", "").strip()
        status_type   = data.get("status_type", "").strip()
        note          = data.get("note", "").strip()

        if not session_id or not university_id or not status_type:
            return jsonify({"ok": False, "msg": "بيانات ناقصة"})

        conn = get_db()
        cur  = conn.cursor()

        cur.execute("SELECT doctor_id, course_name FROM sessions WHERE session_id=?", (session_id,))
        s_row = cur.fetchone()
        if not s_row or s_row["doctor_id"] != session["doctor_id"]:
            conn.close()
            return jsonify({"ok": False, "msg": "غير مصرح"})

        if not student_name:
            cur.execute("SELECT name FROM students WHERE university_id=?", (university_id,))
            st = cur.fetchone()
            student_name = st["name"] if st else university_id

        details = f"نوع الحالة: {status_type}"
        if note:
            details += f" | ملاحظة: {note}"
        details += f" | المادة: {s_row['course_name']} | الدكتور: {session['doctor_name']}"

        cur.execute("""
            INSERT INTO admin_logs (student_id, student_name, action, session_id, details)
            VALUES (?, ?, ?, ?, ?)
        """, (university_id, student_name, f"تقرير حالة: {status_type}", session_id, details))

        conn.commit()
        conn.close()

        return jsonify({"ok": True, "student_name": student_name})
