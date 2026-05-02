import sqlite3
import datetime
import json
import time

import numpy as np
import cv2

from config import DATABASE


# ================= DB =================
def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")

    return conn


# ================= FACE =================
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def enhance_lighting_bgr(img):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l2 = clahe.apply(l)

    merged = cv2.merge((l2, a, b))
    out = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    gamma = 1.15
    table = np.array([
        ((i / 255.0) ** (1.0 / gamma)) * 255
        for i in range(256)
    ]).astype("uint8")

    return cv2.LUT(out, table)


# ================= PERF =================
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
        "min_dist": round(float(min_dist), 4) if min_dist is not None else None,
        "threshold": RECOG_THRESHOLD
    }


# ================= SESSION =================
def _validate_time_hhmm(s):
    s = (s or "").strip()
    if not s or ":" not in s:
        return False

    try:
        hh, mm = map(int, s.split(":"))
        return 0 <= hh <= 23 and 0 <= mm <= 59
    except Exception:
        return False


def _parse_hhmm_to_today(now_dt, hhmm, default_h=8, default_m=0):
    try:
        if hhmm and ":" in str(hhmm):
            hh, mm = map(int, str(hhmm).strip().split(":"))
            return now_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
    except Exception:
        pass

    return now_dt.replace(hour=default_h, minute=default_m, second=0, microsecond=0)


def _get_session_row(session_id):
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT session_id,
                   doctor_id,
                   course_name,
                   COALESCE(start_time, '') AS start_time,
                   COALESCE(end_time, '') AS end_time,
                   COALESCE(session_number, '') AS session_number,
                   COALESCE(room_name, '') AS room_name,
                   COALESCE(room_code, '') AS room_code
            FROM sessions
            WHERE session_id=?
            LIMIT 1
        """, (session_id,))
        return cur.fetchone()
    finally:
        if conn:
            conn.close()


# ================= CACHE =================
_student_ids = []
_student_embs = None
_last_cache_load = 0.0
CACHE_REFRESH_SECONDS = 60


def _load_student_face_cache(force=False):
    global _student_ids, _student_embs, _last_cache_load

    now = time.time()
    if (not force) and _student_embs is not None and (now - _last_cache_load) < CACHE_REFRESH_SECONDS:
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

    ids = []
    embs = []

    for r in rows:
        try:
            uid = str(r["university_id"])
            enc = json.loads(r["face_encoding"])
            arr = np.array(enc, dtype=np.float32)

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


# ================= CONFIG =================
FACE_DETECT_SCALE = 0.5
FACE_MIN_SIZE = (80, 80)
RECOG_THRESHOLD = 0.9
MIN_REG_IMAGES = 12


# ================= LOG =================
def log_admin_activity(student_id, student_name, action, session_id=None, details=None):
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO admin_logs (student_id, student_name, action, session_id, details)
            VALUES (?, ?, ?, ?, ?)
        """, (student_id, student_name, action, session_id, details))
        conn.commit()
    except Exception as e:
        print(f"خطأ في تسجيل نشاط الإدارة: {e}")
    finally:
        if conn:
            conn.close()