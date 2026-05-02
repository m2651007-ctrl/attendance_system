from flask import render_template, request, redirect, session
import sqlite3, datetime, os, smtplib
from email.mime.text import MIMEText

from helpers import get_db, log_admin_activity


ABSENCE_WARNING_THRESHOLD = 0.15
ABSENCE_DEPRIVATION_THRESHOLD = 0.25
DEFAULT_COURSE_LECTURES = 33


def register_student_routes(app):

    # ================= INIT =================
    def ensure_student_section_tables():
        conn = get_db()
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(students)")
        cols = {r["name"] for r in cur.fetchall()}
        if "email" not in cols:
            cur.execute("ALTER TABLE students ADD COLUMN email TEXT")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS student_absence_appeals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_id INTEGER,
                university_id TEXT,
                reason TEXT,
                status TEXT DEFAULT 'pending'
            )
        """)

        conn.commit()
        conn.close()

    ensure_student_section_tables()

    # ================= LOGIN =================
    @app.route("/student/login", methods=["GET", "POST"])
    def student_login():
        if request.method == "POST":
            uid = request.form.get("university_id")

            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM students WHERE university_id=?", (uid,))
            stu = cur.fetchone()
            conn.close()

            if not stu:
                return render_template("student/student_login.html", error="الطالب غير موجود")

            session["student_id"] = uid
            session["student_name"] = stu["name"]
            return redirect("/student/dashboard")

        return render_template("student/student_login.html")

    # ================= LOGOUT =================
    @app.route("/student/logout")
    def student_logout():
        session.clear()
        return redirect("/student/login")

    # ================= DASHBOARD =================
    @app.route("/student/dashboard")
    def student_dashboard():
        if "student_id" not in session:
            return redirect("/student/login")

        return render_template("student/student_dashboard.html")

    # ================= ATTENDANCE =================
    @app.route("/student/attendance")
    def student_attendance_page():
        if "student_id" not in session:
            return redirect("/student/login")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM attendance
            WHERE university_id=?
            ORDER BY id DESC
        """, (session["student_id"],))
        rows = cur.fetchall()
        conn.close()

        return render_template("student/student_attendance.html", attendance=rows)

    # ================= APPEALS =================
    @app.route("/student/appeals")
    def student_appeals_page():
        if "student_id" not in session:
            return redirect("/student/login")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM student_absence_appeals
            WHERE university_id=?
        """, (session["student_id"],))
        rows = cur.fetchall()
        conn.close()

        return render_template("student/student_appeals.html", appeals=rows)

    # ================= CREATE APPEAL =================
    @app.route("/student/appeals/create", methods=["POST"])
    def student_create_appeal():
        attendance_id = request.form.get("attendance_id")
        reason = request.form.get("reason")

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO student_absence_appeals (attendance_id, university_id, reason)
            VALUES (?, ?, ?)
        """, (attendance_id, session["student_id"], reason))

        conn.commit()
        conn.close()

        return redirect("/student/appeals")