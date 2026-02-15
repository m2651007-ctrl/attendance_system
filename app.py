from flask import Flask, render_template, request, redirect, session, jsonify, send_file
import sqlite3, hashlib, csv, io, json, datetime, base64, time
import numpy as np
import cv2

from config import DATABASE, SECRET_KEY
from models.facenet_model import get_face_embedding

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ================= Face Detector =================
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# ================= Lighting Enhancement =================
def enhance_lighting_bgr(img):
    """
    تحسين إضاءة/تباين للصورة (BGR) عشان الوجه يطلع أوضح.
    CLAHE + Gamma (سريع ومفيد للتسجيل والتعرف).
    """
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)

    merged = cv2.merge((l2, a, b))
    out = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    gamma = 1.15
    table = np.array([((i / 255.0) ** (1.0 / gamma)) * 255 for i in range(256)]).astype("uint8")
    out = cv2.LUT(out, table)
    return out

# ================= SPEED CONFIG =================
FACE_DETECT_SCALE = 0.5
FACE_MIN_SIZE = (80, 80)

# ملاحظة: غالباً facenet (L2 distance) يكون threshold حوالين 0.8~1.1 حسب النموذج
RECOG_THRESHOLD = 0.9

CACHE_REFRESH_SECONDS = 60

# ✅ تسجيل الوجه: عدد صور أعلى (يحسن الدقة)
MIN_REG_IMAGES = 12

# ================= STUDENT FACE CACHE =================
_student_ids = []
_student_embs = None
_last_cache_load = 0.0

# ================= SQLITE CONFIG =================
SQLITE_TIMEOUT = 10

def get_db():
    """
    اتصال SQLite مضبوط لتقليل مشكلة database is locked:
    - timeout: ينتظر لو القاعدة مشغولة
    - check_same_thread=False: يسمح لفلَاسك/ثريدز
    - WAL: يسمح قراءة وكتابة أفضل
    """
    conn = sqlite3.connect(DATABASE, timeout=SQLITE_TIMEOUT, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA busy_timeout=5000;")  # ms
    return conn

def ensure_indexes():
    """
    أهم نقطة: INSERT OR REPLACE ما "يستبدل" إلا لو فيه UNIQUE على university_id
    هذا يحل مشكلة تكرار نفس الطالب في جدول student_faces.
    """
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_student_faces_uid
            ON student_faces(university_id);
        """)
        conn.commit()
    finally:
        if conn:
            conn.close()

ensure_indexes()

def _load_student_face_cache(force=False):
    global _student_ids, _student_embs, _last_cache_load

    now = time.time()
    if (not force) and (now - _last_cache_load) < CACHE_REFRESH_SECONDS:
        return

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT university_id, face_encoding FROM student_faces")
        rows = cur.fetchall()
    finally:
        if conn:
            conn.close()

    ids, embs = [], []
    for r in rows:
        uid = str(r["university_id"])
        enc_json = r["face_encoding"]
        try:
            arr = np.array(json.loads(enc_json), dtype=np.float32)
            if arr.ndim == 1 and arr.size > 0:
                ids.append(uid)
                embs.append(arr)
        except Exception:
            continue

    _student_ids = ids
    _student_embs = np.vstack(embs).astype(np.float32) if embs else None
    _last_cache_load = now

def _get_cached_students():
    _load_student_face_cache(force=False)
    return _student_ids, _student_embs

# تحميل الكاش عند تشغيل السيرفر
_load_student_face_cache(force=True)

# ================= PERF HELPERS =================
def _perf_now():
    return time.perf_counter()

def _perf_ms(a, b):
    return round((b - a) * 1000, 2)

def _build_perf(t0, t_decode, t_enh, t_det, t_emb, t_match, min_dist=None):
    return {
        "ms_total": _perf_ms(t0, t_match),
        "ms_decode": _perf_ms(t0, t_decode),
        "ms_enhance": _perf_ms(t_decode, t_enh),
        "ms_detect": _perf_ms(t_enh, t_det),
        "ms_embed": _perf_ms(t_det, t_emb),
        "ms_match": _perf_ms(t_emb, t_match),
        "min_dist": (round(float(min_dist), 4) if min_dist is not None else None),
        "threshold": RECOG_THRESHOLD
    }

def _parse_hhmm_to_today(now_dt, hhmm, default_h=8, default_m=0):
    """يحـوّل HH:MM إلى datetime بنفس اليوم."""
    try:
        if hhmm and ":" in str(hhmm):
            hh, mm = map(int, str(hhmm).strip().split(":"))
            return now_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
    except Exception:
        pass
    return now_dt.replace(hour=default_h, minute=default_m, second=0, microsecond=0)

def _validate_time_hhmm(s):
    s = (s or "").strip()
    if not s or ":" not in s:
        return False
    try:
        hh, mm = map(int, s.split(":"))
        return 0 <= hh <= 23 and 0 <= mm <= 59
    except Exception:
        return False

def _get_session_row(session_id):
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT session_id, doctor_id, course_name,
                   COALESCE(start_time,'') AS start_time,
                   COALESCE(end_time,'') AS end_time
            FROM sessions
            WHERE session_id=?
            LIMIT 1
        """, (session_id,))
        return cur.fetchone()
    finally:
        if conn:
            conn.close()

# ================= DEBUG HELPERS =================
@app.route("/debug/dbpath")
def debug_dbpath():
    # عشان تتأكد إنك فاتح نفس ملف DB في DB Browser
    return jsonify({"db_path": DATABASE})

@app.route("/debug/wal_checkpoint")
def debug_wal_checkpoint():
    # مفيد لو DB Browser ما يقرأ التحديثات بسبب WAL
    conn = None
    try:
        conn = get_db()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        return jsonify({"ok": True, "message": "WAL checkpoint done"})
    finally:
        if conn:
            conn.close()

# ================= HOME =================
@app.route("/")
def home():
    return redirect("/admin/login")

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

        return "Invalid login", 401

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

# ================= ADMIN PAGES =================
@app.route("/admin/students")
def admin_students():
    if "admin" not in session:
        return redirect("/admin/login")
    return render_template("admin/admin_students.html")

@app.route("/admin/attendance")
def admin_attendance():
    if "admin" not in session:
        return redirect("/admin/login")
    return render_template("admin/admin_attendance.html")

# ✅ ديناميكي: عدد الصور المطلوب في التسجيل
@app.route("/admin/register_student_face/config")
def register_student_face_config():
    if "admin" not in session:
        return jsonify({"ok": False}), 401
    return jsonify({"ok": True, "min_images": MIN_REG_IMAGES})

# ✅ اختبار سرعة/دقة التعرف (بدون تسجيل حضور)
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
        return jsonify({"ok": True, "recognized": False, "perf": perf, "message": "No face detected"})

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

# ✅ Admin import attendance CSV (page + upload)
@app.route("/admin/attendance/import", methods=["GET", "POST"])
def admin_attendance_import():
    if "admin" not in session:
        return redirect("/admin/login")

    if request.method == "GET":
        return render_template("admin/admin_attendance_import.html")

    file = request.files.get("file")
    if not file:
        return "No file uploaded", 400

    content = file.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    required_cols = {"session_id", "university_id", "check_in", "status"}
    if not required_cols.issubset(set(reader.fieldnames or [])):
        return f"CSV columns must include: {sorted(list(required_cols))}", 400

    inserted = 0
    skipped = 0

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()

        for row in reader:
            session_id = str(row.get("session_id", "")).strip()
            university_id = str(row.get("university_id", "")).strip()
            check_in_v = str(row.get("check_in", "")).strip()
            status = str(row.get("status", "")).strip()

            if not session_id or not university_id or not check_in_v:
                skipped += 1
                continue

            cur.execute("""
                SELECT id FROM attendance
                WHERE session_id=? AND university_id=? AND date(check_in)=date(?)
                LIMIT 1
            """, (session_id, university_id, check_in_v))
            existed = cur.fetchone()

            if existed:
                skipped += 1
                continue

            cur.execute("""
                INSERT INTO attendance (session_id, university_id, check_in, status)
                VALUES (?, ?, ?, ?)
            """, (session_id, university_id, check_in_v, status))
            inserted += 1

        conn.commit()
    finally:
        if conn:
            conn.close()

    return f"Imported: {inserted} | Skipped: {skipped}"

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
            SELECT s.session_id, s.course_name, d.name, s.active,
                   COALESCE(s.start_time, '') AS start_time,
                   COALESCE(s.end_time, '') AS end_time
            FROM sessions s
            JOIN doctors d ON s.doctor_id = d.doctor_id
            ORDER BY s.session_id DESC
        """)
        sessions = cur.fetchall()
    finally:
        if conn:
            conn.close()

    return render_template("admin/admin_courses.html", doctors=doctors, sessions=sessions)

# ✅ إضافة Session
@app.route("/admin/sessions/add", methods=["POST"])
def admin_sessions_add():
    if "admin" not in session:
        return redirect("/admin/login")

    course_name = (request.form.get("course_name") or "").strip()
    doctor_id = (request.form.get("doctor_id") or "").strip()
    start_time = (request.form.get("start_time") or "").strip()
    end_time = (request.form.get("end_time") or "").strip()

    if not course_name or not doctor_id:
        return "Missing course_name/doctor_id", 400

    if not _validate_time_hhmm(start_time) or not _validate_time_hhmm(end_time):
        return "Invalid start_time/end_time (expected HH:MM)", 400

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sessions (course_name, doctor_id, start_time, end_time, active)
            VALUES (?, ?, ?, ?, 1)
        """, (course_name, doctor_id, start_time, end_time))
        conn.commit()
    finally:
        if conn:
            conn.close()

    return redirect("/admin/courses")

# ✅ حذف Session
@app.route("/admin/sessions/delete/<int:session_id>")
def admin_sessions_delete(session_id):
    if "admin" not in session:
        return redirect("/admin/login")

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
        conn.commit()
    finally:
        if conn:
            conn.close()

    return redirect("/admin/courses")

# ================= ADMIN DOCTORS =================
@app.route("/admin/doctors")
def admin_doctors():
    if "admin" not in session:
        return redirect("/admin/login")

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT doctor_id, name, email, username FROM doctors")
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
        cur.execute("SELECT doctor_id FROM doctors WHERE username=? OR email=?", (username, email))
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

        # سجل الطالب إن ما كان موجود
        cur.execute(
            "INSERT OR IGNORE INTO students (university_id, name, academic_number) VALUES (?, ?, ?)",
            (university_id, name, university_id)
        )

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

                if len(faces) > 0:
                    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                    x, y, w, h = int(x / scale), int(y / scale), int(w / scale), int(h / scale)
                    face = img[y:y+h, x:x+w]
                else:
                    # لو ما اكتشف وجه في صورة معينة، تجاهلها
                    continue

                face = cv2.resize(face, (160, 160))
                emb = get_face_embedding(face)
                embeddings.append(emb)
                used += 1
            except Exception:
                continue

        if used < max(5, MIN_REG_IMAGES // 2):
            return jsonify({"message": f"تم رفض التسجيل: تم استخدام {used} صور فقط (الوجه غير واضح)"}), 400

        final_embedding = np.mean(embeddings, axis=0)

        # ✅ UPSERT مضمون مع UNIQUE index
        cur.execute("""
            INSERT INTO student_faces (university_id, face_encoding)
            VALUES (?, ?)
            ON CONFLICT(university_id) DO UPDATE SET
                face_encoding=excluded.face_encoding
        """, (university_id, json.dumps(final_embedding.tolist())))

        conn.commit()

    except sqlite3.OperationalError as e:
        return jsonify({"message": f"❌ DB Error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

    _load_student_face_cache(force=True)
    return jsonify({"message": "✅ تم تسجيل الطالب ووجهه بنجاح", "images_used": used})

# ===================== DOCTOR AUTH =====================
@app.route("/doctor/login", methods=["GET", "POST"])
def doctor_login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT doctor_id, name, password_hash FROM doctors WHERE username=?", (username,))
            doctor = cur.fetchone()
        finally:
            if conn:
                conn.close()

        if doctor and hashlib.sha256(password.encode()).hexdigest() == doctor["password_hash"]:
            session["doctor_id"] = doctor["doctor_id"]
            session["doctor_name"] = doctor["name"]
            return redirect("/doctor/dashboard")

        return render_template("doctor/login.html", error="اسم المستخدم أو كلمة المرور غير صحيحة")

    return render_template("doctor/login.html")

@app.route("/doctor/dashboard")
def doctor_dashboard():
    if "doctor_id" not in session:
        return redirect("/doctor/login")
    return render_template("doctor/doctor_dashboard.html", doctor_name=session.get("doctor_name"))

@app.route("/doctor/courses")
def doctor_courses():
    if "doctor_id" not in session:
        return redirect("/doctor/login")

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT course_name, session_id,
                   COALESCE(start_time,'') AS start_time,
                   COALESCE(end_time,'') AS end_time
            FROM sessions
            WHERE doctor_id=?
            ORDER BY session_id DESC
        """, (session["doctor_id"],))
        rows = cur.fetchall()
    finally:
        if conn:
            conn.close()

    courses = []
    for r in rows:
        courses.append({
            "course_code": r["course_name"],
            "course_name": r["course_name"],
            "section_name": r["session_id"],
            "start_time": r["start_time"],
            "end_time": r["end_time"],
        })

    return render_template("doctor/doctor_courses.html", courses=courses)

# =================== ATTENDANCE PAGE ===================
@app.route("/doctor/attendance")
def doctor_attendance():
    if "doctor_id" not in session:
        return redirect("/doctor/login")

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT session_id, course_name,
                   COALESCE(start_time,'') AS start_time,
                   COALESCE(end_time,'') AS end_time
            FROM sessions
            WHERE doctor_id=?
            ORDER BY session_id DESC
        """, (session["doctor_id"],))
        sessions = cur.fetchall()

        cur.execute("""
            SELECT s.name, se.course_name, a.check_in, a.check_out, a.status
            FROM attendance a
            JOIN students s ON a.university_id = s.university_id
            JOIN sessions se ON a.session_id = se.session_id
            WHERE se.doctor_id=?
            ORDER BY a.id DESC
        """, (session["doctor_id"],))
        attendance = cur.fetchall()
    finally:
        if conn:
            conn.close()

    return render_template("doctor/doctor_attendance.html", sessions=sessions, attendance=attendance)

@app.route("/doctor/attendance/list")
def doctor_attendance_list():
    if "doctor_id" not in session:
        return jsonify({"ok": False, "message": "Unauthorized"}), 401

    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"ok": True, "rows": []})

    # ✅ تأكد أن الحصة للدكتور
    se = _get_session_row(session_id)
    if not se or int(se["doctor_id"]) != int(session["doctor_id"]):
        return jsonify({"ok": False, "message": "Session not found for this doctor"}), 403

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT st.name, st.academic_number, st.university_id, a.check_in, a.status
            FROM attendance a
            JOIN students st ON a.university_id = st.university_id
            WHERE a.session_id=?
            ORDER BY a.id DESC
        """, (session_id,))
        rows = cur.fetchall()
    finally:
        if conn:
            conn.close()

    out = []
    for r in rows:
        out.append({
            "name": r["name"],
            "academic_number": r["academic_number"],
            "university_id": r["university_id"],
            "check_in": str(r["check_in"]),
            "status": r["status"]
        })
    return jsonify({"ok": True, "rows": out})

@app.route("/doctor/attendance/export")
def doctor_attendance_export():
    if "doctor_id" not in session:
        return redirect("/doctor/login")

    session_id = request.args.get("session_id")
    if not session_id:
        return "Missing session_id", 400

    se = _get_session_row(session_id)
    if not se or int(se["doctor_id"]) != int(session["doctor_id"]):
        return "Unauthorized", 403

    course_name = se["course_name"]

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT a.session_id, st.university_id, st.name, st.academic_number, a.check_in, a.status
            FROM attendance a
            JOIN students st ON a.university_id = st.university_id
            WHERE a.session_id=?
            ORDER BY a.id ASC
        """, (session_id,))
        rows = cur.fetchall()
    finally:
        if conn:
            conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["session_id", "university_id", "name", "academic_number", "check_in", "status"])
    for r in rows:
        writer.writerow([r["session_id"], r["university_id"], r["name"], r["academic_number"], r["check_in"], r["status"]])

    csv_bytes = io.BytesIO(output.getvalue().encode("utf-8-sig"))
    csv_bytes.seek(0)

    safe_course = "".join([c for c in str(course_name) if c.isalnum() or c in ("_", "-", " ")])
    filename = f"attendance_session_{session_id}_{safe_course}.csv"
    return send_file(csv_bytes, mimetype="text/csv", as_attachment=True, download_name=filename)

# =================== ATTENDANCE CAPTURE (CHECK-IN) ===================
@app.route("/doctor/attendance/capture", methods=["POST"])
def doctor_attendance_capture():
    if "doctor_id" not in session:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.json or {}
    image_data = data.get("image")
    session_id = data.get("session_id")

    if not image_data or not session_id:
        return jsonify({"ok": False, "message": "Missing image/session"}), 400

    # ✅ تأكد إن الحصة للدكتور (هذا سبب شائع أنه "ما يتعرف" لأنه session غلط)
    se = _get_session_row(session_id)
    if not se or int(se["doctor_id"]) != int(session["doctor_id"]):
        return jsonify({"ok": False, "message": "Session not found for this doctor"}), 403

    t0 = _perf_now()

    img_bytes = base64.b64decode(image_data.split(",")[1])
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    t_decode = _perf_now()

    if img is None:
        return jsonify({"ok": False, "message": "Invalid image"}), 400

    img = enhance_lighting_bgr(img)
    t_enh = _perf_now()

    scale = FACE_DETECT_SCALE
    small = cv2.resize(img, (0, 0), fx=scale, fy=scale)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=FACE_MIN_SIZE)
    t_det = _perf_now()

    if len(faces) == 0:
        perf = _build_perf(t0, t_decode, t_enh, t_det, t_det, t_det, None)
        return jsonify({"ok": True, "recognized": False, "perf": perf, "message": "No face detected"})

    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    x, y, w, h = int(x / scale), int(y / scale), int(w / scale), int(h / scale)

    face_img = img[y:y+h, x:x+w]
    face_img = cv2.resize(face_img, (160, 160))
    embedding = get_face_embedding(face_img).astype(np.float32)
    t_emb = _perf_now()

    student_ids, student_embs = _get_cached_students()
    if student_embs is None or len(student_ids) == 0:
        return jsonify({"ok": False, "message": "No cached student faces (register students first)"}), 500

    dists = np.linalg.norm(student_embs - embedding, axis=1)
    best_idx = int(np.argmin(dists))
    min_dist = float(dists[best_idx])
    t_match = _perf_now()

    perf = _build_perf(t0, t_decode, t_enh, t_det, t_emb, t_match, min_dist)

    if min_dist >= RECOG_THRESHOLD:
        return jsonify({
            "ok": True,
            "recognized": False,
            "box": [int(x), int(y), int(w), int(h)],
            "perf": perf
        })

    matched_id = str(student_ids[best_idx])

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT name, academic_number FROM students WHERE university_id=?", (matched_id,))
        stu = cur.fetchone()
        student_name = stu["name"] if stu else "طالب"
        academic_number = stu["academic_number"] if stu else matched_id

        now = datetime.datetime.now()

        lecture_start = _parse_hhmm_to_today(now, se["start_time"], default_h=8, default_m=0)
        diff = (now - lecture_start).total_seconds() / 60.0

        if diff <= 10:
            status = "Present"
        elif diff <= 20:
            status = "Late"
        else:
            status = "Absent"

        cur.execute("""
            SELECT id FROM attendance
            WHERE session_id=? AND university_id=? AND date(check_in)=date(?)
            ORDER BY id DESC LIMIT 1
        """, (session_id, matched_id, now))
        existed = cur.fetchone()

        new_record = False
        if not existed:
            cur.execute("""
                INSERT INTO attendance (session_id, university_id, check_in, status)
                VALUES (?, ?, ?, ?)
            """, (session_id, matched_id, now, status))
            conn.commit()
            new_record = True

    except sqlite3.OperationalError as e:
        return jsonify({"ok": False, "message": f"DB Error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

    return jsonify({
        "ok": True,
        "recognized": True,
        "new_record": new_record,
        "box": [int(x), int(y), int(w), int(h)],
        "student": {
            "name": student_name,
            "academic_number": academic_number,
            "university_id": matched_id,
            "status": status
        },
        "perf": perf
    })

# =================== CHECKOUT PAGE ===================
@app.route("/doctor/attendance/checkout_page")
def doctor_checkout_page():
    if "doctor_id" not in session:
        return redirect("/doctor/login")

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT session_id, course_name,
                   COALESCE(start_time,'') AS start_time,
                   COALESCE(end_time,'') AS end_time
            FROM sessions
            WHERE doctor_id=?
            ORDER BY session_id DESC
        """, (session["doctor_id"],))
        sessions = cur.fetchall()
    finally:
        if conn:
            conn.close()

    return render_template("doctor/doctor_checkout.html", sessions=sessions)

@app.route("/doctor/attendance/checkout/list")
def doctor_checkout_list():
    if "doctor_id" not in session:
        return jsonify({"ok": False, "message": "Unauthorized"}), 401

    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"ok": True, "rows": []})

    se = _get_session_row(session_id)
    if not se or int(se["doctor_id"]) != int(session["doctor_id"]):
        return jsonify({"ok": False, "message": "Session not found for this doctor"}), 403

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT st.name, st.academic_number, st.university_id, a.check_in, a.check_out, a.status
            FROM attendance a
            JOIN students st ON a.university_id = st.university_id
            WHERE a.session_id=?
            ORDER BY a.id DESC
        """, (session_id,))
        rows = cur.fetchall()
    finally:
        if conn:
            conn.close()

    out = []
    for r in rows:
        out.append({
            "name": r["name"],
            "academic_number": r["academic_number"],
            "university_id": r["university_id"],
            "check_in": str(r["check_in"]),
            "check_out": (str(r["check_out"]) if r["check_out"] else ""),
            "status": r["status"]
        })
    return jsonify({"ok": True, "rows": out})

# =================== CHECKOUT CAPTURE (CHECK-OUT) ===================
@app.route("/doctor/attendance/checkout/capture", methods=["POST"])
def doctor_attendance_checkout_capture():
    if "doctor_id" not in session:
        return jsonify({"message": "Unauthorized"}), 401

    data = request.json or {}
    image_data = data.get("image")
    session_id = data.get("session_id")

    if not image_data or not session_id:
        return jsonify({"ok": False, "message": "Missing image/session"}), 400

    se = _get_session_row(session_id)
    if not se or int(se["doctor_id"]) != int(session["doctor_id"]):
        return jsonify({"ok": False, "message": "Session not found for this doctor"}), 403

    t0 = _perf_now()

    img_bytes = base64.b64decode(image_data.split(",")[1])
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    t_decode = _perf_now()

    if img is None:
        return jsonify({"ok": False, "message": "Invalid image"}), 400

    img = enhance_lighting_bgr(img)
    t_enh = _perf_now()

    scale = FACE_DETECT_SCALE
    small = cv2.resize(img, (0, 0), fx=scale, fy=scale)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=FACE_MIN_SIZE)
    t_det = _perf_now()

    if len(faces) == 0:
        perf = _build_perf(t0, t_decode, t_enh, t_det, t_det, t_det, None)
        return jsonify({"ok": True, "recognized": False, "perf": perf, "message": "No face detected"})

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

    if min_dist >= RECOG_THRESHOLD:
        return jsonify({"ok": True, "recognized": False, "perf": perf})

    matched_id = str(student_ids[best_idx])

    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()

        now = datetime.datetime.now()

        cur.execute("""
            SELECT id FROM attendance
            WHERE session_id=? AND university_id=?
              AND date(check_in)=date(?)
              AND (check_out IS NULL OR TRIM(check_out)='')
            ORDER BY id DESC LIMIT 1
        """, (session_id, matched_id, now))
        row = cur.fetchone()

        checked_out = False
        if row:
            att_id = row["id"]
            cur.execute("UPDATE attendance SET check_out=? WHERE id=?", (now, att_id))
            conn.commit()
            checked_out = True

    except sqlite3.OperationalError as e:
        return jsonify({"ok": False, "message": f"DB Error: {str(e)}"}), 500
    finally:
        if conn:
            conn.close()

    return jsonify({
        "ok": True,
        "recognized": True,
        "checked_out": checked_out,
        "student": {"university_id": matched_id},
        "perf": perf
    })

@app.route("/doctor/logout")
def doctor_logout():
    session.clear()
    return redirect("/doctor/login")

# ================= RUN =================
if __name__ == "__main__":
    print("DB PATH =>", DATABASE)
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False, threaded=True)
