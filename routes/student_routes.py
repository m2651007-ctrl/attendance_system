from flask import render_template, request, redirect, session
import sqlite3
import datetime
import os
import smtplib
import hashlib
from email.mime.text import MIMEText

from helpers import get_db, log_admin_activity


ABSENCE_WARNING_THRESHOLD = 0.15
ABSENCE_DEPRIVATION_THRESHOLD = 0.25
DEFAULT_COURSE_LECTURES = 33


def _student_status_is_absent(status_value):
    raw = (status_value or "").strip().lower()
    if not raw:
        return False
    return any(token in raw for token in ["absent", "غياب", "غائب"])


def _student_is_valid_email(email_value):
    email_value = (email_value or "").strip()
    return "@" in email_value and "." in email_value and len(email_value) <= 255


def _student_hash_password(password_value):
    return hashlib.sha256((password_value or "").encode()).hexdigest()


def _student_validate_strong_password(password_value):
    password_value = password_value or ""
    if len(password_value) < 8:
        return False, "كلمة المرور يجب أن تكون 8 أحرف على الأقل"
    if not any(ch.islower() for ch in password_value):
        return False, "كلمة المرور يجب أن تحتوي على حرف صغير واحد على الأقل"
    if not any(ch.isupper() for ch in password_value):
        return False, "كلمة المرور يجب أن تحتوي على حرف كبير واحد على الأقل"
    if not any(ch.isdigit() for ch in password_value):
        return False, "كلمة المرور يجب أن تحتوي على رقم واحد على الأقل"
    if not any(not ch.isalnum() for ch in password_value):
        return False, "كلمة المرور يجب أن تحتوي على رمز خاص واحد على الأقل"
    return True, ""


def _student_send_email_notification(to_email, subject, body):
    smtp_host = (os.environ.get("STUDENT_SMTP_HOST") or "").strip()
    smtp_port = int((os.environ.get("STUDENT_SMTP_PORT") or "587").strip() or "587")
    smtp_user = (os.environ.get("STUDENT_SMTP_USER") or "").strip()
    smtp_pass = (os.environ.get("STUDENT_SMTP_PASS") or "").strip()
    smtp_sender = (os.environ.get("STUDENT_SMTP_SENDER") or smtp_user).strip()

    if not smtp_host or not smtp_user or not smtp_pass or not smtp_sender:
        return False, "missing_smtp_env"

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_sender
    msg["To"] = to_email

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_sender, [to_email], msg.as_string())
        return True, "sent"
    except Exception as ex:
        return False, str(ex)


def _student_process_alert_event(student_id, student_name, student_email, risk_level, absence_rate_percent, risk_course_name=""):
    if risk_level not in ("warning", "deprived"):
        return {"created": False, "email_attempted": False, "email_sent": False}

    alert_date = datetime.date.today().isoformat()
    email_ok = _student_is_valid_email(student_email)
    conn = None
    event_id = None
    created = False

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO student_alert_events (university_id, alert_level, alert_date, email_to)
            VALUES (?, ?, ?, ?)
        """, (student_id, risk_level, alert_date, student_email if email_ok else ""))
        conn.commit()
        event_id = cur.lastrowid
        created = True
    except sqlite3.IntegrityError:
        try:
            if conn is None:
                conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                SELECT id, COALESCE(email_sent, 0) AS email_sent
                FROM student_alert_events
                WHERE university_id=? AND alert_level=? AND alert_date=?
                LIMIT 1
            """, (student_id, risk_level, alert_date))
            existing = cur.fetchone()
            if not existing:
                return {"created": False, "email_attempted": False, "email_sent": False}
            event_id = int(existing["id"])
            if int(existing["email_sent"]) == 1:
                return {"created": False, "email_attempted": False, "email_sent": True}
            cur.execute(
                "UPDATE student_alert_events SET email_to=? WHERE id=?",
                (student_email if email_ok else "", event_id)
            )
            conn.commit()
            created = False
        finally:
            if conn:
                conn.close()
                conn = None
    finally:
        if conn:
            conn.close()

    if not email_ok:
        log_admin_activity(
            student_id,
            student_name,
            "STUDENT_ALERT_CREATED_NO_EMAIL",
            details=f"level={risk_level},date={alert_date},rate={absence_rate_percent}%,course={risk_course_name}"
        )
        return {"created": created, "email_attempted": False, "email_sent": False}

    subject = "تنبيه الغياب | Attendance Alert"
    if risk_level == "deprived":
        subject = "إشعار الحرمان | Deprivation Alert"

    risk_label_ar = "قرب من الحرمان" if risk_level == "warning" else "حرمان"
    risk_label_en = "Near Deprivation" if risk_level == "warning" else "Deprivation"
    body = (
        f"مرحبًا {student_name}\n"
        f"هذه رسالة آلية من نظام الحضور.\n"
        f"حالتك الحالية: {risk_label_ar}\n"
        f"نسبة الغياب الحالية: {absence_rate_percent}%\n"
        f"المقرر الأكثر تأثرًا: {risk_course_name or '-'}\n\n"
        f"Hello {student_name},\n"
        f"This is an automated message from the attendance system.\n"
        f"Your current status: {risk_label_en}\n"
        f"Current absence rate: {absence_rate_percent}%\n"
        f"Most affected course: {risk_course_name or '-'}\n"
    )

    sent, send_message = _student_send_email_notification(student_email, subject, body)

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE student_alert_events SET email_sent=? WHERE id=?", (1 if sent else 0, event_id))
        conn.commit()
    finally:
        if conn:
            conn.close()

    log_admin_activity(
        student_id,
        student_name,
        "STUDENT_ALERT_EMAIL_SENT" if sent else "STUDENT_ALERT_EMAIL_FAILED",
        details=f"level={risk_level},date={alert_date},course={risk_course_name},message={send_message}"
    )
    return {"created": created, "email_attempted": True, "email_sent": bool(sent)}


def _student_collect_page_data(student_id, msg="", msg_type="info", process_alerts=False):
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "SELECT name, COALESCE(email, '') AS email FROM students WHERE university_id=? LIMIT 1",
            (student_id,)
        )
        student = cur.fetchone()

        cur.execute("""
            SELECT
                a.id AS attendance_id,
                COALESCE(se.course_name, '-') AS course_name,
                COALESCE(a.check_in, '') AS check_in,
                COALESCE(a.check_out, '') AS check_out,
                COALESCE(a.status, '') AS status,
                COALESCE(ap.status, '') AS appeal_status,
                COALESCE(ap.reason, '') AS appeal_reason,
                COALESCE(ap.admin_note, '') AS appeal_admin_note,
                COALESCE(ap.reviewed_at, '') AS appeal_reviewed_at,
                COALESCE(ap.created_at, '') AS appeal_created_at
            FROM attendance a
            LEFT JOIN sessions se ON se.session_id = a.session_id
            LEFT JOIN student_absence_appeals ap
                ON ap.attendance_id = a.id
               AND ap.university_id = a.university_id
            WHERE a.university_id=?
            ORDER BY a.id DESC
        """, (student_id,))
        attendance_rows = cur.fetchall()
    finally:
        if conn:
            conn.close()

    student_name = student["name"] if student else session.get("student_name", "طالب")
    student_email = student["email"] if student else ""
    total_sessions = len(attendance_rows)
    absent_count = sum(1 for row in attendance_rows if _student_status_is_absent(row["status"]))
    present_count = max(total_sessions - absent_count, 0)

    course_map = {}
    for row in attendance_rows:
        course_name = (row["course_name"] or "-").strip() or "-"
        if course_name not in course_map:
            course_map[course_name] = {"course_name": course_name, "absent_count": 0}
        if _student_status_is_absent(row["status"]):
            course_map[course_name]["absent_count"] += 1

    course_stats = []
    for item in course_map.values():
        rate = item["absent_count"] / float(DEFAULT_COURSE_LECTURES)
        course_stats.append({
            "course_name": item["course_name"],
            "absent_count": item["absent_count"],
            "expected_lectures": DEFAULT_COURSE_LECTURES,
            "absence_rate": rate,
            "absence_rate_percent": round(rate * 100, 2)
        })
    course_stats.sort(key=lambda x: x["absence_rate"], reverse=True)
    top_risk_course = course_stats[0] if course_stats else None
    absence_rate = top_risk_course["absence_rate"] if top_risk_course else 0.0

    risk_level = "safe"
    alerts = []
    if total_sessions == 0:
        alerts.append({"type": "info", "text": "لا توجد سجلات حضور حتى الآن."})
    elif absence_rate >= ABSENCE_DEPRIVATION_THRESHOLD:
        risk_level = "deprived"
        alerts.append({"type": "danger", "text": f"تم تجاوز حد الحرمان في مقرر: {top_risk_course['course_name'] if top_risk_course else '-'}."})
    elif absence_rate >= ABSENCE_WARNING_THRESHOLD:
        risk_level = "warning"
        alerts.append({"type": "warning", "text": f"تنبيه: نسبة الغياب قريبة من الحرمان في مقرر: {top_risk_course['course_name'] if top_risk_course else '-'}."})

    if risk_level in ("warning", "deprived") and not student_email:
        alerts.append({"type": "info", "text": "لا يوجد بريد إلكتروني مسجل لتفعيل تنبيهات البريد."})

    alert_event = {"created": False, "email_attempted": False, "email_sent": False}
    if process_alerts:
        alert_event = _student_process_alert_event(
            student_id=student_id,
            student_name=student_name,
            student_email=student_email,
            risk_level=risk_level,
            absence_rate_percent=round(absence_rate * 100, 2),
            risk_course_name=(top_risk_course["course_name"] if top_risk_course else "")
        )

    appeals_rows = [row for row in attendance_rows if (row["appeal_status"] or "").strip()]

    return {
        "student_name": student_name,
        "student_id": student_id,
        "student_email": student_email,
        "total_sessions": total_sessions,
        "present_count": present_count,
        "absent_count": absent_count,
        "absence_rate_percent": round(absence_rate * 100, 2),
        "top_risk_course_name": top_risk_course["course_name"] if top_risk_course else "-",
        "default_course_lectures": DEFAULT_COURSE_LECTURES,
        "course_stats": course_stats,
        "risk_level": risk_level,
        "alerts": alerts,
        "alert_event": alert_event,
        "attendance": attendance_rows,
        "appeals": appeals_rows,
        "msg": msg,
        "msg_type": msg_type
    }


def register_student_routes(app):
    def ensure_student_section_tables():
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("PRAGMA table_info(students)")
            cols = {r["name"] for r in cur.fetchall()}
            if "email" not in cols:
                cur.execute("ALTER TABLE students ADD COLUMN email TEXT")
            if "password_hash" not in cols:
                cur.execute("ALTER TABLE students ADD COLUMN password_hash TEXT")

            cur.execute("SELECT university_id FROM students WHERE password_hash IS NULL OR TRIM(password_hash)=''")
            for row in cur.fetchall():
                cur.execute(
                    "UPDATE students SET password_hash=? WHERE university_id=?",
                    (_student_hash_password(str(row["university_id"])), row["university_id"])
                )

            cur.execute("""
                CREATE TABLE IF NOT EXISTS student_absence_appeals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attendance_id INTEGER NOT NULL,
                    university_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    admin_note TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at DATETIME,
                    UNIQUE(attendance_id, university_id)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_student_appeals_student ON student_absence_appeals(university_id)")

            cur.execute("PRAGMA table_info(student_absence_appeals)")
            appeal_cols = {r["name"] for r in cur.fetchall()}
            if "admin_note" not in appeal_cols:
                cur.execute("ALTER TABLE student_absence_appeals ADD COLUMN admin_note TEXT")
            if "created_at" not in appeal_cols:
                cur.execute("ALTER TABLE student_absence_appeals ADD COLUMN created_at DATETIME")
            if "reviewed_at" not in appeal_cols:
                cur.execute("ALTER TABLE student_absence_appeals ADD COLUMN reviewed_at DATETIME")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS student_alert_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    university_id TEXT NOT NULL,
                    alert_level TEXT NOT NULL,
                    alert_date TEXT NOT NULL,
                    email_to TEXT,
                    email_sent INTEGER NOT NULL DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(university_id, alert_level, alert_date)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_student_alert_events_student ON student_alert_events(university_id)")

            cur.execute("PRAGMA table_info(student_alert_events)")
            alert_cols = {r["name"] for r in cur.fetchall()}
            if "email_to" not in alert_cols:
                cur.execute("ALTER TABLE student_alert_events ADD COLUMN email_to TEXT")
            if "email_sent" not in alert_cols:
                cur.execute("ALTER TABLE student_alert_events ADD COLUMN email_sent INTEGER NOT NULL DEFAULT 0")
            if "created_at" not in alert_cols:
                cur.execute("ALTER TABLE student_alert_events ADD COLUMN created_at DATETIME")

            conn.commit()
        finally:
            if conn:
                conn.close()

    ensure_student_section_tables()

    @app.route("/student/login", methods=["GET", "POST"])
    def student_login():
        if request.method == "POST":
            uid = (request.form.get("university_id") or "").strip()
            password = request.form.get("password") or ""

            if not uid or not password:
                return render_template("student/student_login.html", error="الرقم الجامعي وكلمة المرور مطلوبان")

            conn = None
            try:
                conn = get_db()
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT university_id, name
                    FROM students
                    WHERE university_id=? AND password_hash=?
                    LIMIT 1
                    """,
                    (uid, _student_hash_password(password))
                )
                stu = cur.fetchone()
            finally:
                if conn:
                    conn.close()

            if not stu:
                return render_template("student/student_login.html", error="الرقم الجامعي أو كلمة المرور غير صحيحة")

            session["student_id"] = stu["university_id"]
            session["student_name"] = stu["name"]
            return redirect("/student/dashboard")

        return render_template("student/student_login.html")

    @app.route("/student/logout")
    def student_logout():
        session.pop("student_id", None)
        session.pop("student_name", None)
        return redirect("/student/login")

    @app.route("/student/dashboard")
    def student_dashboard():
        if "student_id" not in session:
            return redirect("/student/login")
        page_data = _student_collect_page_data(str(session["student_id"]), (request.args.get("msg") or "").strip(), (request.args.get("msg_type") or "info").strip(), True)
        return render_template("student/student_dashboard.html", **page_data, nav_page="dashboard")

    @app.route("/student/attendance")
    def student_attendance_page():
        if "student_id" not in session:
            return redirect("/student/login")
        page_data = _student_collect_page_data(str(session["student_id"]), (request.args.get("msg") or "").strip(), (request.args.get("msg_type") or "info").strip(), False)
        return render_template("student/student_attendance.html", **page_data, nav_page="attendance")

    @app.route("/student/appeals")
    def student_appeals_page():
        if "student_id" not in session:
            return redirect("/student/login")
        page_data = _student_collect_page_data(str(session["student_id"]), (request.args.get("msg") or "").strip(), (request.args.get("msg_type") or "info").strip(), False)
        return render_template("student/student_appeals.html", **page_data, nav_page="appeals")

    @app.route("/student/alerts")
    def student_alerts_page():
        if "student_id" not in session:
            return redirect("/student/login")
        page_data = _student_collect_page_data(str(session["student_id"]), (request.args.get("msg") or "").strip(), (request.args.get("msg_type") or "info").strip(), True)
        return render_template("student/student_alerts.html", **page_data, nav_page="alerts")

    @app.route("/student/profile/email", methods=["POST"])
    def student_update_email():
        if "student_id" not in session:
            return redirect("/student/login")

        student_id = str(session["student_id"])
        email_value = (request.form.get("email") or "").strip()
        if email_value and not _student_is_valid_email(email_value):
            return redirect("/student/alerts?msg=البريد الإلكتروني غير صالح&msg_type=danger")

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE students SET email=? WHERE university_id=?", (email_value, student_id))
            conn.commit()
        finally:
            if conn:
                conn.close()

        return redirect("/student/alerts?msg=تم تحديث البريد الإلكتروني&msg_type=success")

    @app.route("/student/profile/password", methods=["POST"])
    def student_update_password():
        if "student_id" not in session:
            return redirect("/student/login")

        student_id = str(session["student_id"])
        current_password = request.form.get("current_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not current_password or not new_password or not confirm_password:
            return redirect("/student/alerts?msg=جميع حقول كلمة المرور مطلوبة&msg_type=danger")
        if new_password != confirm_password:
            return redirect("/student/alerts?msg=تأكيد كلمة المرور غير مطابق&msg_type=danger")
        if current_password == new_password:
            return redirect("/student/alerts?msg=كلمة المرور الجديدة يجب أن تكون مختلفة عن الحالية&msg_type=warning")

        is_strong, password_message = _student_validate_strong_password(new_password)
        if not is_strong:
            return redirect(f"/student/alerts?msg={password_message}&msg_type=danger")

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT COALESCE(password_hash,'') AS password_hash, COALESCE(name,'طالب') AS name FROM students WHERE university_id=? LIMIT 1", (student_id,))
            student_row = cur.fetchone()
            if not student_row:
                return redirect("/student/login")
            if student_row["password_hash"] != _student_hash_password(current_password):
                return redirect("/student/alerts?msg=كلمة المرور الحالية غير صحيحة&msg_type=danger")

            cur.execute("UPDATE students SET password_hash=? WHERE university_id=?", (_student_hash_password(new_password), student_id))
            conn.commit()
        finally:
            if conn:
                conn.close()

        log_admin_activity(student_id, student_row["name"], "STUDENT_PASSWORD_CHANGED", details="password changed from student portal")
        return redirect("/student/alerts?msg=تم تغيير كلمة المرور بنجاح&msg_type=success")

    @app.route("/student/appeals/create", methods=["POST"])
    def student_create_appeal():
        if "student_id" not in session:
            return redirect("/student/login")

        student_id = str(session["student_id"])
        attendance_id_raw = (request.form.get("attendance_id") or "").strip()
        reason = (request.form.get("reason") or "").strip()

        if not attendance_id_raw.isdigit():
            return redirect("/student/attendance?msg=رقم السجل غير صالح&msg_type=danger")
        if len(reason) < 10:
            return redirect("/student/attendance?msg=سبب الاعتراض يجب أن يكون أوضح (10 أحرف على الأقل)&msg_type=danger")
        if len(reason) > 1000:
            return redirect("/student/attendance?msg=سبب الاعتراض طويل جدًا&msg_type=danger")

        attendance_id = int(attendance_id_raw)
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT id, status FROM attendance WHERE id=? AND university_id=? LIMIT 1", (attendance_id, student_id))
            attendance_row = cur.fetchone()
            if not attendance_row:
                return redirect("/student/attendance?msg=سجل الحضور غير موجود&msg_type=danger")
            if not _student_status_is_absent(attendance_row["status"]):
                return redirect("/student/attendance?msg=الاعتراض متاح على حالات الغياب فقط&msg_type=danger")

            cur.execute("""
                INSERT INTO student_absence_appeals (attendance_id, university_id, reason, status)
                VALUES (?, ?, ?, 'pending')
            """, (attendance_id, student_id, reason))
            log_admin_activity(student_id, session.get("student_name", "طالب"), "ABSENCE_APPEAL_SUBMITTED", details=f"attendance_id={attendance_id}")
            conn.commit()
        except sqlite3.IntegrityError:
            return redirect("/student/attendance?msg=تم إرسال اعتراض مسبقًا على هذا الغياب&msg_type=warning")
        finally:
            if conn:
                conn.close()

        return redirect("/student/attendance?msg=تم إرسال الاعتراض للإدارة بنجاح&msg_type=success")
