from flask import render_template, request, redirect, session, jsonify, send_file
import sqlite3, hashlib, csv, io, json, datetime, base64
import numpy as np
import cv2

from helpers import (
    get_db,
    _validate_time_hhmm,
    enhance_lighting_bgr,
    face_cascade,
    MIN_REG_IMAGES,
    _load_student_face_cache,
    _get_cached_students,
    _perf_now,
    _build_perf,
    FACE_DETECT_SCALE,
    FACE_MIN_SIZE,
    RECOG_THRESHOLD,
    log_admin_activity
)

from models.facenet_model import get_face_embedding


def _validate_room_code(room_code):
    room_code = (room_code or "").strip()
    return room_code.isdigit() and len(room_code) == 6


def ensure_session_extra_columns():
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(sessions)")
        cols = [c["name"] for c in cur.fetchall()]

        if "session_number" not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN session_number TEXT")

        if "room_name" not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN room_name TEXT")

        if "room_code" not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN room_code TEXT")

        if "days" not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN days TEXT")

        if "capacity" not in cols:
            cur.execute("ALTER TABLE sessions ADD COLUMN capacity INTEGER")

        conn.commit()
    finally:
        if conn:
            conn.close()


def register_admin_routes(app):

    ensure_session_extra_columns()

    # ================= ADMIN AUTH =================
    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            password_hash = hashlib.sha256(password.encode()).hexdigest()

            conn = None
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    "SELECT id FROM admins WHERE username=? AND password_hash=?",
                    (username, password_hash)
                )
                row = cur.fetchone()
            finally:
                if conn:
                    conn.close()

            if row:
                session["admin"] = username
                return redirect("/admin/dashboard")

            return render_template("admin/admin_login.html", error="اسم المستخدم أو كلمة المرور غير صحيحة")

        return render_template("admin/admin_login.html")


    @app.route("/admin/logout")
    def admin_logout():
        session.pop("admin", None)
        return redirect("/admin/login")


    @app.route("/admin/dashboard")
    def admin_dashboard():
        if "admin" not in session:
            return redirect("/admin/login")
        return render_template("admin/admin_dashboard.html")

# ================= ADMIN APPEALS =================
    @app.route("/admin/appeals")
    def admin_appeals():
        if "admin" not in session:
            return redirect("/admin/login")

        status_filter = (request.args.get("status") or "all").strip().lower()
        if status_filter not in {"all", "pending", "approved", "rejected"}:
            status_filter = "all"

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            query = """
                SELECT
                    ap.id,
                    ap.attendance_id,
                    ap.university_id,
                    COALESCE(st.name, '-') AS student_name,
                    COALESCE(se.course_name, '-') AS course_name,
                    COALESCE(a.check_in, '') AS check_in,
                    COALESCE(a.status, '') AS attendance_status,
                    ap.reason,
                    ap.status,
                    COALESCE(ap.admin_note, '') AS admin_note,
                    COALESCE(ap.created_at, '') AS created_at,
                    COALESCE(ap.reviewed_at, '') AS reviewed_at
                FROM student_absence_appeals ap
                LEFT JOIN attendance a ON a.id = ap.attendance_id
                LEFT JOIN sessions se ON se.session_id = a.session_id
                LEFT JOIN students st ON st.university_id = ap.university_id
            """
            params = []
            if status_filter != "all":
                query += " WHERE ap.status=?"
                params.append(status_filter)
            query += " ORDER BY CASE WHEN ap.status='pending' THEN 0 ELSE 1 END, ap.id DESC"
            cur.execute(query, params)
            appeals = cur.fetchall()
        finally:
            if conn:
                conn.close()

        return render_template("admin/admin_appeals.html", appeals=appeals, status_filter=status_filter)


    @app.route("/admin/appeals/<int:appeal_id>/review", methods=["POST"])
    def admin_review_appeal(appeal_id):
        if "admin" not in session:
            return redirect("/admin/login")

        decision = (request.form.get("decision") or "").strip().lower()
        admin_note = (request.form.get("admin_note") or "").strip()
        if decision not in ("approved", "rejected"):
            return redirect("/admin/appeals?status=pending")

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT ap.id, ap.status, ap.university_id, ap.attendance_id,
                       COALESCE(st.name, 'طالب') AS student_name
                FROM student_absence_appeals ap
                LEFT JOIN students st ON st.university_id = ap.university_id
                WHERE ap.id=?
                LIMIT 1
            """, (appeal_id,))
            appeal = cur.fetchone()
            if not appeal:
                return redirect("/admin/appeals?status=pending")
            if (appeal["status"] or "") != "pending":
                return redirect("/admin/appeals?status=all")

            cur.execute("""
                UPDATE student_absence_appeals
                SET status=?, admin_note=?, reviewed_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (decision, admin_note, appeal_id))

            if decision == "approved":
                cur.execute(
                    "UPDATE attendance SET status='Present (Appeal Approved)' WHERE id=?",
                    (appeal["attendance_id"],)
                )

            log_admin_activity(
                appeal["university_id"],
                appeal["student_name"],
                "ABSENCE_APPEAL_APPROVED" if decision == "approved" else "ABSENCE_APPEAL_REJECTED",
                details=f"appeal_id={appeal_id},attendance_id={appeal['attendance_id']},note={admin_note}"
            )
            conn.commit()
        finally:
            if conn:
                conn.close()

        return redirect("/admin/appeals?status=pending")
    
    # ================= ADMIN PAGES =================
    @app.route("/admin/students")
    def admin_students():
        if "admin" not in session:
            return redirect("/admin/login")

        conn = get_db()
        cur = conn.cursor()

        # 1. Total Registered Students - direct database count
        cur.execute("SELECT COUNT(*) FROM students")
        total_students = cur.fetchone()[0]

        # 2. Today's Registrations - count from students table using created_at
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        cur.execute("""
            SELECT COUNT(*) FROM students 
            WHERE DATE(created_at) = ?
        """, (today,))
        today_registrations = cur.fetchone()[0]

        # 3. Face Recognition Accuracy - simplified calculation
        cur.execute("""
            SELECT COUNT(*) as total_attempts,
                   SUM(CASE 
                       WHEN details LIKE '%result: success%' AND details LIKE '%confidence:%' THEN
                           CAST(SUBSTR(details, 
                               INSTR(details, 'confidence:') + 11, 
                               INSTR(SUBSTR(details, INSTR(details, 'confidence:') + 11), ',') - 1
                           ) AS REAL)
                       ELSE 0
                   END) as total_confidence
            FROM admin_logs 
            WHERE action = 'FACE_RECOGNITION' 
            AND DATE(timestamp) = ?
        """, (today,))
        recognition_data = cur.fetchone()
        
        if recognition_data[0] > 0 and recognition_data[1] > 0:
            recognition_accuracy = round(recognition_data[1] / recognition_data[0], 1)
        else:
            # Check last 7 days for historical data
            week_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
            cur.execute("""
                SELECT COUNT(*) as total_attempts,
                       SUM(CASE 
                           WHEN details LIKE '%result: success%' AND details LIKE '%confidence:%' THEN
                               CAST(SUBSTR(details, 
                                   INSTR(details, 'confidence:') + 11, 
                                   INSTR(SUBSTR(details, INSTR(details, 'confidence:') + 11), ',') - 1
                           ) AS REAL)
                       ELSE 0
                       END) as total_confidence
                FROM admin_logs 
                WHERE action = 'FACE_RECOGNITION' 
                AND DATE(timestamp) >= ?
            """, (week_ago,))
            week_data = cur.fetchone()
            
            if week_data[0] > 0 and week_data[1] > 0:
                recognition_accuracy = round(week_data[1] / week_data[0], 1)
            else:
                # Use threshold as baseline if no recognition data
                recognition_accuracy = round(RECOG_THRESHOLD * 100, 1)

        # 4. Last Update - current system date
        last_update = datetime.datetime.now().strftime('%B %d')

        conn.close()

        return render_template(
            "admin/admin_students.html",
            total_students=total_students,
            today_registrations=today_registrations,
            recognition_accuracy=recognition_accuracy,
            last_update=last_update
        )


    # ================= ADMIN DOCTORS =================
    @app.route("/admin/doctors")
    def admin_doctors():
        if "admin" not in session:
            return redirect("/admin/login")

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT doctor_id, name, email, username
                FROM doctors
                ORDER BY doctor_id DESC
            """)
            doctors = cur.fetchall()
        finally:
            if conn:
                conn.close()

        return render_template("admin/admin_doctors.html", doctors=doctors)


    @app.route("/admin/doctors/add", methods=["POST"])
    def add_doctor():
        if "admin" not in session:
            return redirect("/admin/login")

        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        if not name or not email or not username or not password:
            return "Missing data", 400

        password_hash = hashlib.sha256(password.encode()).hexdigest()

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("""
                SELECT doctor_id
                FROM doctors
                WHERE username=? OR email=?
                LIMIT 1
            """, (username, email))

            if cur.fetchone():
                return "Username or email already exists", 400

            cur.execute("""
                INSERT INTO doctors (name, email, username, password_hash)
                VALUES (?, ?, ?, ?)
            """, (name, email, username, password_hash))

            conn.commit()
        finally:
            if conn:
                conn.close()

        return redirect("/admin/doctors")


    @app.route("/admin/doctors/delete/<int:doctor_id>")
    def delete_doctor(doctor_id):
        if "admin" not in session:
            return redirect("/admin/login")

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("DELETE FROM doctors WHERE doctor_id=?", (doctor_id,))
            conn.commit()
        finally:
            if conn:
                conn.close()

        return redirect("/admin/doctors")


    @app.route("/admin/attendance")
    def admin_attendance():
        if "admin" not in session:
            return redirect("/admin/login")
        return render_template("admin/admin_attendance.html")


    @app.route("/admin/attendance/data")
    def admin_attendance_data():
        if "admin" not in session:
            return jsonify({"ok": False, "message": "Unauthorized"}), 401

        course_search = request.args.get("course_search", "").strip()
        student_search = request.args.get("student_search", "").strip()

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            query = """
                SELECT a.id, a.session_id, a.university_id, a.check_in, a.check_out, a.status,
                       s.name AS student_name, s.academic_number,
                       sess.course_name,
                       COALESCE(sess.session_number, '') AS session_number,
                       sess.start_time AS session_start_time,
                       sess.end_time AS session_end_time,
                       d.name AS instructor_name
                FROM attendance a
                JOIN students s ON a.university_id = s.university_id
                JOIN sessions sess ON a.session_id = sess.session_id
                JOIN doctors d ON sess.doctor_id = d.doctor_id
            """

            params = []
            where_conditions = []

            if course_search:
                where_conditions.append("""
                    (
                        sess.course_name LIKE ?
                        OR CAST(sess.session_id AS TEXT) LIKE ?
                        OR COALESCE(sess.session_number, '') LIKE ?
                    )
                """)
                params.extend([f"%{course_search}%", f"%{course_search}%", f"%{course_search}%"])

            if student_search:
                where_conditions.append("a.university_id LIKE ?")
                params.append(f"%{student_search}%")

            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)

            query += " ORDER BY a.check_in DESC LIMIT 2000"
            cur.execute(query, params)
            rows = cur.fetchall()

        finally:
            if conn:
                conn.close()

        records = []
        for r in rows:
            final_status = r["status"]

            if r["check_in"] and r["session_start_time"]:
                try:
                    check_in = datetime.datetime.fromisoformat(r["check_in"].replace("Z", "+00:00"))
                    hours, minutes = r["session_start_time"].split(":")
                    session_start = check_in.replace(
                        hour=int(hours),
                        minute=int(minutes),
                        second=0,
                        microsecond=0
                    )
                    diff_minutes = (check_in - session_start).total_seconds() / 60

                    if diff_minutes > 15 and r["status"] == "Present":
                        final_status = "Late"
                except Exception:
                    pass

            records.append({
                "id": r["id"],
                "session_id": r["session_id"],
                "session_number": r["session_number"],
                "university_id": r["university_id"],
                "student_name": r["student_name"],
                "academic_number": r["academic_number"],
                "course_name": r["course_name"],
                "session_start_time": r["session_start_time"],
                "session_end_time": r["session_end_time"],
                "instructor_name": r["instructor_name"],
                "check_in": r["check_in"],
                "check_out": r["check_out"],
                "status": final_status
            })

        return jsonify({"ok": True, "records": records})


    @app.route("/admin/attendance/delete", methods=["POST"])
    def admin_attendance_delete():
        if "admin" not in session:
            return jsonify({"ok": False, "message": "Unauthorized"}), 401

        data = request.json or {}
        record_ids = data.get("record_ids", [])

        if not record_ids:
            return jsonify({"ok": False, "message": "No record IDs provided"}), 400

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            placeholders = ",".join(["?" for _ in record_ids])
            cur.execute(f"DELETE FROM attendance WHERE id IN ({placeholders})", record_ids)
            deleted_count = cur.rowcount
            conn.commit()

            return jsonify({"ok": True, "deleted_count": deleted_count})
        except Exception as e:
            if conn:
                conn.rollback()
            return jsonify({"ok": False, "message": f"Error deleting records: {str(e)}"}), 500
        finally:
            if conn:
                conn.close()


    @app.route("/admin/attendance/export")
    def admin_attendance_export():
        if "admin" not in session:
            return redirect("/admin/login")

        course_search = request.args.get("course_search", "").strip()
        student_search = request.args.get("student_search", "").strip()
        selected_ids = request.args.get("selected_ids", "").strip()

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            query = """
                SELECT a.id, a.session_id, a.university_id, a.check_in, a.check_out, a.status,
                       s.name AS student_name, s.academic_number,
                       sess.course_name,
                       COALESCE(sess.session_number, '') AS session_number,
                       sess.start_time AS session_start_time,
                       sess.end_time AS session_end_time,
                       d.name AS instructor_name
                FROM attendance a
                JOIN students s ON a.university_id = s.university_id
                JOIN sessions sess ON a.session_id = sess.session_id
                JOIN doctors d ON sess.doctor_id = d.doctor_id
            """

            params = []
            where_conditions = []

            if course_search:
                where_conditions.append("""
                    (
                        sess.course_name LIKE ?
                        OR CAST(sess.session_id AS TEXT) LIKE ?
                        OR COALESCE(sess.session_number, '') LIKE ?
                    )
                """)
                params.extend([f"%{course_search}%", f"%{course_search}%", f"%{course_search}%"])

            if student_search:
                where_conditions.append("a.university_id LIKE ?")
                params.append(f"%{student_search}%")

            if selected_ids:
                ids = selected_ids.split(",")
                where_conditions.append("a.id IN ({})".format(",".join(["?" for _ in ids])))
                params.extend(ids)

            if where_conditions:
                query += " WHERE " + " AND ".join(where_conditions)

            query += " ORDER BY a.check_in DESC"
            cur.execute(query, params)
            rows = cur.fetchall()

        finally:
            if conn:
                conn.close()

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Student Name",
            "Student ID",
            "Course Name",
            "Session ID",
            "Session Number",
            "Instructor Name",
            "Check-in Time",
            "Check-out Time",
            "Status"
        ])

        for r in rows:
            final_status = r["status"]

            if r["check_in"] and r["session_start_time"]:
                try:
                    check_in = datetime.datetime.fromisoformat(r["check_in"].replace("Z", "+00:00"))
                    hours, minutes = r["session_start_time"].split(":")
                    session_start = check_in.replace(
                        hour=int(hours),
                        minute=int(minutes),
                        second=0,
                        microsecond=0
                    )
                    diff_minutes = (check_in - session_start).total_seconds() / 60

                    if diff_minutes > 15 and r["status"] == "Present":
                        final_status = "Late"
                except Exception:
                    pass

            checkout_display = r["check_out"] if r["check_out"] else "Not Checked Out" if r["check_in"] else "-"

            writer.writerow([
                r["student_name"],
                r["university_id"],
                r["course_name"],
                r["session_id"],
                r["session_number"] or "-",
                r["instructor_name"],
                r["check_in"] or "-",
                checkout_display,
                final_status
            ])

        csv_bytes = io.BytesIO(output.getvalue().encode("utf-8-sig"))
        csv_bytes.seek(0)

        filename = f"attendance_records_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return send_file(
            csv_bytes,
            mimetype="text/csv",
            as_attachment=True,
            download_name=filename
        )


    # ================= ADMIN COURSES / SESSIONS =================
    @app.route("/admin/courses")
    def admin_courses():
        if "admin" not in session:
            return redirect("/admin/login")

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("SELECT doctor_id, name FROM doctors")
            doctors = cur.fetchall()

            cur.execute("""
                SELECT s.session_id,
                       s.course_name,
                       COALESCE(s.session_number, '') AS session_number,
                       d.name AS doctor_name,
                       s.active,
                       COALESCE(s.start_time, '') AS start_time,
                       COALESCE(s.end_time, '') AS end_time,
                       COALESCE(s.room_name, '') AS room_name,
                       COALESCE(s.room_code, '') AS room_code,
                       COALESCE(s.days, '') AS days,
                       COALESCE(s.capacity, 0) AS capacity
                FROM sessions s
                JOIN doctors d ON s.doctor_id = d.doctor_id
                ORDER BY s.session_id DESC
            """)
            sessions = cur.fetchall()
        finally:
            if conn:
                conn.close()

        return render_template("admin/admin_courses.html", doctors=doctors, sessions=sessions)


    @app.route("/admin/sessions/add", methods=["POST"])
    def admin_sessions_add():
        if "admin" not in session:
            return redirect("/admin/login")

        course_name = (request.form.get("course_name") or "").strip()
        session_number = (request.form.get("session_number") or "").strip()
        doctor_id = (request.form.get("doctor_id") or "").strip()
        start_time = (request.form.get("start_time") or "").strip()
        end_time = (request.form.get("end_time") or "").strip()
        room_name = (request.form.get("room_name") or "").strip()
        room_code = (request.form.get("room_code") or "").strip()

        if not course_name or not doctor_id or not session_number:
            return "Missing course_name/doctor_id/session_number", 400

        if not _validate_time_hhmm(start_time) or not _validate_time_hhmm(end_time):
            return "Invalid start_time/end_time (expected HH:MM)", 400

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sessions
                    (course_name, session_number, doctor_id, start_time, end_time, active, room_name, room_code)
                VALUES
                    (?, ?, ?, ?, ?, 1, ?, ?)
            """, (
                course_name,
                session_number,
                doctor_id,
                start_time,
                end_time,
                room_name,
                room_code
            ))
            conn.commit()
        finally:
            if conn:
                conn.close()

        return redirect("/admin/courses")


    @app.route("/admin/sessions/delete/<int:session_id>")
    def admin_sessions_delete(session_id):
        if "admin" not in session:
            return redirect("/admin/login")

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            # احذف السجلات المرتبطة أولاً
            cur.execute("DELETE FROM attendance WHERE session_id=?", (session_id,))
            cur.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
            conn.commit()
        finally:
            if conn:
                conn.close()

        return redirect("/admin/courses")


    # ================= ADMIN LOGS =================
    @app.route("/admin/logs")
    def admin_logs():
        if "admin" not in session:
            return redirect("/admin/login")
        return render_template("admin/admin_logs.html")


    @app.route("/admin/logs/data")
    def admin_logs_data():
        if "admin" not in session:
            return jsonify({"ok": False, "message": "Unauthorized"}), 401

        search_student_id = request.args.get("search_student_id", "").strip()

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            query = """
                SELECT
                    al.id,
                    al.student_id,
                    al.student_name,
                    al.action,
                    al.timestamp,
                    al.session_id,
                    al.details,
                    COALESCE(s.course_name, '') AS course_name,
                    COALESCE(s.session_number, '') AS session_number
                FROM admin_logs al
                LEFT JOIN sessions s ON al.session_id = s.session_id
            """

            params = []

            if search_student_id:
                query += " WHERE al.student_id LIKE ?"
                params.append(f"%{search_student_id}%")

            query += " ORDER BY CASE WHEN al.action='SPOOF_ATTEMPT_DETECTED' THEN 0 ELSE 1 END, al.timestamp DESC LIMIT 1000"
            cur.execute(query, params)
            rows = cur.fetchall()

        finally:
            if conn:
                conn.close()

        logs = []
        for r in rows:
            logs.append({
                "id": r["id"],
                "student_id": r["student_id"],
                "student_name": r["student_name"],
                "action": r["action"],
                "timestamp": r["timestamp"],
                "session_id": r["session_id"],
                "session_number": r["session_number"],
                "details": r["details"],
                "course_name": r["course_name"]
            })

        return jsonify({"ok": True, "logs": logs})


    @app.route("/admin/logs/delete", methods=["POST"])
    def admin_logs_delete():
        if "admin" not in session:
            return jsonify({"ok": False, "message": "Unauthorized"}), 401

        data = request.json or {}
        log_ids = data.get("log_ids", [])

        if not log_ids:
            return jsonify({"ok": False, "message": "No log IDs provided"}), 400

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            placeholders = ",".join(["?" for _ in log_ids])
            cur.execute(f"DELETE FROM admin_logs WHERE id IN ({placeholders})", log_ids)
            deleted_count = cur.rowcount
            conn.commit()

            return jsonify({"ok": True, "deleted_count": deleted_count})
        except Exception as e:
            if conn:
                conn.rollback()
            return jsonify({"ok": False, "message": f"Error deleting logs: {str(e)}"}), 500
        finally:
            if conn:
                conn.close()


    @app.route("/admin/logs/export")
    def admin_logs_export():
        if "admin" not in session:
            return redirect("/admin/login")

        search_student_id = request.args.get("search_student_id", "").strip()

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            query = """
                SELECT
                    al.id,
                    al.student_id,
                    al.student_name,
                    al.action,
                    al.timestamp,
                    al.session_id,
                    al.details,
                    COALESCE(s.course_name, '') AS course_name,
                    COALESCE(s.session_number, '') AS session_number
                FROM admin_logs al
                LEFT JOIN sessions s ON al.session_id = s.session_id
            """

            params = []

            if search_student_id:
                query += " WHERE al.student_id LIKE ?"
                params.append(f"%{search_student_id}%")

            query += " ORDER BY al.timestamp DESC"
            cur.execute(query, params)
            rows = cur.fetchall()

        finally:
            if conn:
                conn.close()

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "Student ID",
            "Student Name",
            "Course Name",
            "Session ID",
            "Session Number",
            "Action",
            "Timestamp",
            "Details"
        ])

        for r in rows:
            writer.writerow([
                r["student_id"],
                r["student_name"],
                r["course_name"] or "-",
                r["session_id"] or "-",
                r["session_number"] or "-",
                r["action"],
                r["timestamp"],
                r["details"] or "-"
            ])

        csv_bytes = io.BytesIO(output.getvalue().encode("utf-8-sig"))
        csv_bytes.seek(0)

        filename = f"admin_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        return send_file(
            csv_bytes,
            mimetype="text/csv",
            as_attachment=True,
            download_name=filename
        )


    # ================= ADMIN FACE CONFIG / TEST =================
    @app.route("/admin/register_student_face/config")
    def register_student_face_config():
        if "admin" not in session:
            return jsonify({"ok": False}), 401
        return jsonify({"ok": True, "min_images": MIN_REG_IMAGES})


    # ================= ADMIN RECOGNITION TEST =================
    @app.route("/admin/recognition_test", methods=["POST"])
    def admin_recognition_test():
        if "admin" not in session:
            return jsonify({"ok": False, "message": "Unauthorized"}), 401

        data = request.json or {}
        image_data = data.get("image")

        if not image_data:
            return jsonify({"ok": False, "message": "Missing image"}), 400

        t0 = _perf_now()

        img_bytes = base64.b64decode(image_data.split(",")[1])
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        t_decode = _perf_now()

        img = enhance_lighting_bgr(img)
        t_enh = _perf_now()

        scale = FACE_DETECT_SCALE
        small = cv2.resize(img, (0, 0), fx=scale, fy=scale)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=FACE_MIN_SIZE)
        t_det = _perf_now()

        if len(faces) == 0:
            perf = _build_perf(t0, t_decode, t_enh, t_det, t_det, t_det, None)
            return jsonify({
                "ok": True,
                "recognized": False,
                "perf": perf,
                "message": "No face detected"
            })

        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        x, y, w, h = int(x / scale), int(y / scale), int(w / scale), int(h / scale)

        face_img = img[y:y+h, x:x+w]
        face_img = cv2.resize(face_img, (160, 160))
        embedding = get_face_embedding(face_img).astype(np.float32)
        t_emb = _perf_now()

        student_ids, student_embs = _get_cached_students()

        if student_embs is None or len(student_ids) == 0:
            return jsonify({"ok": False, "message": "No cached student faces"}), 500

        dists = np.linalg.norm(student_embs - embedding, axis=1)
        best_idx = int(np.argmin(dists))
        min_dist = float(dists[best_idx])
        t_match = _perf_now()

        perf = _build_perf(t0, t_decode, t_enh, t_det, t_emb, t_match, min_dist)

        recognized = (min_dist < RECOG_THRESHOLD)
        matched_id = str(student_ids[best_idx]) if recognized else None

        return jsonify({
            "ok": True,
            "recognized": recognized,
            "matched_university_id": matched_id,
            "box": [int(x), int(y), int(w), int(h)],
            "perf": perf
        })


    # ================= REGISTER STUDENT FACE =================
    @app.route("/admin/register_student_face", methods=["POST"])
    def register_student_face():
        if "admin" not in session:
            return jsonify({"message": "Unauthorized"}), 401

        data = request.json or {}
        name = (data.get("name") or "").strip()
        university_id = (data.get("university_id") or "").strip()
        images = data.get("images", []) or []

        if not name or not university_id:
            return jsonify({"message": "لازم الاسم + الرقم الجامعي"}), 400

        if len(images) < MIN_REG_IMAGES:
            return jsonify({"message": f"لازم {MIN_REG_IMAGES} صور على الأقل"}), 400

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("""
                INSERT INTO students (university_id, name, academic_number, password_hash)
                VALUES (?, ?, ?, ?)
            """, (university_id, name, university_id, hashlib.sha256(university_id.encode()).hexdigest()))

            existing = cur.fetchone()

            if existing:
                log_admin_activity(
                    university_id,
                    name,
                    "DUPLICATE_REGISTRATION_ATTEMPT",
                    details="محاولة تسجيل مكرر"
                )
                return jsonify({"message": "الطالب مسجل بالفعل"}), 400

            cur.execute("""
                INSERT INTO students (university_id, name, academic_number, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (university_id, name, university_id))

            embeddings = []
            used = 0

            for img_data in images:
                try:
                    img_bytes = base64.b64decode(img_data.split(",")[1])
                    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)

                    if img is None:
                        continue

                    img = enhance_lighting_bgr(img)

                    scale = 0.7
                    small = cv2.resize(img, (0, 0), fx=scale, fy=scale)
                    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=(80, 80))

                    if len(faces) == 0:
                        continue

                    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                    x, y, w, h = int(x / scale), int(y / scale), int(w / scale), int(h / scale)

                    face = img[y:y+h, x:x+w]
                    face = cv2.resize(face, (160, 160))

                    emb = get_face_embedding(face)
                    embeddings.append(emb)
                    used += 1

                except Exception:
                    continue

            if used < max(5, MIN_REG_IMAGES // 2):
                return jsonify({
                    "message": f"تم رفض التسجيل: فقط {used} صورة صالحة"
                }), 400

            final_embedding = np.mean(embeddings, axis=0)

            cur.execute("""
                INSERT INTO student_faces (university_id, face_encoding)
                VALUES (?, ?)
                ON CONFLICT(university_id)
                DO UPDATE SET face_encoding=excluded.face_encoding
            """, (university_id, json.dumps(final_embedding.tolist())))

            conn.commit()

            # Log successful registration for today's statistics
            log_admin_activity(
                university_id,
                name,
                "STUDENT_REGISTERED",
                details=f"تم تسجيل الطالب بنجاح باستخدام {used} صورة"
            )
        except Exception as e:
            return jsonify({"message": f"❌ خطأ: {str(e)}"}), 500

        finally:
            if conn:
                conn.close()

        _load_student_face_cache(force=True)

        return jsonify({
            "message": "✅ تم تسجيل الطالب بنجاح",
            "images_used": used
        })
