from flask import render_template, request, jsonify
import sqlite3, datetime, base64
import numpy as np
import cv2
from anti_spoofing import AntiSpoofing
_spoof_detector = AntiSpoofing()

# cache لمنع تكرار تسجيل محاولات الحضور المكررة
import time
_duplicate_cache = {}   # {(session_id, uid): last_logged_time}
_DUPLICATE_COOLDOWN = 60  # ثانية

from helpers import (
    get_db,
    enhance_lighting_bgr,
    face_cascade,
    _get_cached_students,
    FACE_DETECT_SCALE,
    FACE_MIN_SIZE,
    RECOG_THRESHOLD,
    log_admin_activity
)

from models.facenet_model import get_face_embedding


def register_kiosk_routes(app):

    # ================= SETUP =================
    @app.route("/kiosk/setup")
    def kiosk_setup():
        conn = None
        try:
            conn = get_db()
            cur  = conn.cursor()
            cur.execute("""
                SELECT DISTINCT room_name
                FROM sessions
                WHERE room_name IS NOT NULL AND room_name != ''
                ORDER BY room_name
            """)
            rooms = [r["room_name"] for r in cur.fetchall()]
        finally:
            if conn: conn.close()

        return render_template("kiosk/kiosk_setup.html", rooms=rooms)

    # ================= CAMERA =================
    @app.route("/kiosk/camera")
    def kiosk_camera():
        return render_template("kiosk/kiosk_camera.html")

    # ================= AUTHORIZE ← كانت ناقصة =================
    @app.route("/kiosk/authorize", methods=["POST"])
    def kiosk_authorize():
        data      = request.json or {}
        room_name = (data.get("room_name") or "").strip()
        room_code = (data.get("room_code") or "").strip()

        if not room_name or not room_code:
            return jsonify({"ok": False, "message": "القاعة والكود مطلوبان"})

        if not room_code.isdigit() or len(room_code) != 6:
            return jsonify({"ok": False, "message": "الكود يجب أن يكون 6 أرقام"})

        conn = None
        try:
            conn = get_db()
            cur  = conn.cursor()
            cur.execute("""
                SELECT session_id FROM sessions
                WHERE room_name = ? AND room_code = ?
                LIMIT 1
            """, (room_name, room_code))
            row = cur.fetchone()
        finally:
            if conn: conn.close()

        if not row:
            return jsonify({"ok": False, "message": "القاعة أو الكود غير صحيح"})

        return jsonify({"ok": True})

    # ================= ACTIVE SESSION ← كانت ناقصة =================
    @app.route("/kiosk/active")
    def kiosk_active():
        room_name = (request.args.get("room_name") or "").strip()
        room_code = (request.args.get("room_code") or "").strip()

        if not room_name or not room_code:
            return jsonify({"ok": False, "message": "بيانات ناقصة"})

        now      = datetime.datetime.now()
        now_time = now.strftime("%H:%M")

        conn = None
        try:
            conn = get_db()
            cur  = conn.cursor()
            cur.execute("""
                SELECT s.session_id, s.course_name,
                       s.start_time, s.end_time,
                       COALESCE(s.session_number, '') AS session_number
                FROM sessions s
                WHERE s.room_name = ?
                  AND s.room_code = ?
                  AND s.active    = 1
                  AND s.start_time <= ?
                  AND s.end_time   >= ?
                LIMIT 1
            """, (room_name, room_code, now_time, now_time))
            row = cur.fetchone()
        finally:
            if conn: conn.close()

        if not row:
            return jsonify({"ok": False, "message": "لا توجد محاضرة نشطة الآن"})

        return jsonify({
            "ok": True,
            "session": {
                "session_id":     row["session_id"],
                "course_name":    row["course_name"],
                "session_number": row["session_number"],
                "start_time":     row["start_time"],
                "end_time":       row["end_time"]
            }
        })

    # ================= CAPTURE =================
    @app.route("/kiosk/capture", methods=["POST"])
    def kiosk_capture():
        data       = request.json or {}
        image_data = data.get("image")
        room_name  = (data.get("room_name") or "").strip()
        room_code  = (data.get("room_code") or "").strip()
        mode       = (data.get("mode") or "checkin").strip()
        blink_detected = bool(data.get("blink_detected", False))

        if not image_data or not room_name or not room_code:
            return jsonify({"ok": False, "message": "بيانات ناقصة"})

        # ── جلب الجلسة النشطة ──
        now      = datetime.datetime.now()
        now_time = now.strftime("%H:%M")

        conn = None
        try:
            conn = get_db()
            cur  = conn.cursor()
            cur.execute("""
                SELECT session_id, course_name, start_time, end_time
                FROM sessions
                WHERE room_name = ? AND room_code = ?
                  AND active = 1
                  AND start_time <= ? AND end_time >= ?
                LIMIT 1
            """, (room_name, room_code, now_time, now_time))
            session_row = cur.fetchone()
        finally:
            if conn: conn.close()

        if not session_row:
            return jsonify({"ok": False, "message": "لا توجد محاضرة نشطة"})

        active_session_id = session_row["session_id"]

        # ── معالجة الصورة ──
        try:
            img_bytes = base64.b64decode(image_data.split(",")[1])
            img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                return jsonify({"ok": True, "recognized": False})
        except Exception:
            return jsonify({"ok": True, "recognized": False})

        img  = enhance_lighting_bgr(img)

        scale = FACE_DETECT_SCALE
        small = cv2.resize(img, (0, 0), fx=scale, fy=scale)
        gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray, 1.2, 5, minSize=FACE_MIN_SIZE
        )

        if len(faces) == 0:
            _spoof_detector.reset()
            return jsonify({"ok": True, "recognized": False})

        # ── Anti-Spoofing Check (with blink tracking) ──
        spoof_result = _spoof_detector.check(img, blink_detected=blink_detected, room_id=room_name)
        if not spoof_result.is_live:
            try:
                log_admin_activity(
                    "UNKNOWN", "مجهول", "SPOOF_ATTEMPT_DETECTED",
                    details=f"room={room_name},reason={spoof_result.reason},score={spoof_result.score}"
                )
            except Exception:
                pass
            return jsonify({
                "ok": True, "recognized": False,
                "spoof_detected": True,
                "spoof_reason": spoof_result.reason,
                "message": "تم رفض الوجه — لا يبدو وجهاً حقيقياً"
            })

        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        x = int(x / scale); y = int(y / scale)
        w = int(w / scale); h = int(h / scale)

        face_img  = cv2.resize(img[y:y+h, x:x+w], (160, 160))
        embedding = get_face_embedding(face_img).astype(np.float32)

        ids, embs = _get_cached_students()
        if embs is None or len(ids) == 0:
            return jsonify({"ok": True, "recognized": False})

        dists    = np.linalg.norm(embs - embedding, axis=1)
        best_idx = int(np.argmin(dists))
        min_dist = float(dists[best_idx])

        if min_dist > RECOG_THRESHOLD:
            return jsonify({
                "ok": True,
                "recognized": False,
                "box": [int(x), int(y), int(w), int(h)]
            })

        uid = str(ids[best_idx])

        conn = None
        try:
            conn = get_db()
            cur  = conn.cursor()

            # ── معلومات الطالب ──
            cur.execute("""
                SELECT name, COALESCE(academic_number, university_id) AS academic_number
                FROM students WHERE university_id = ? LIMIT 1
            """, (uid,))
            stu = cur.fetchone()
            student_info = {
                "name":            stu["name"]            if stu else uid,
                "academic_number": stu["academic_number"] if stu else uid
            }

            # ── وضع الانصراف ──
            if mode == "checkout":
                cur.execute("""
                    SELECT id, check_out FROM attendance
                    WHERE session_id = ? AND university_id = ?
                    ORDER BY id DESC LIMIT 1
                """, (active_session_id, uid))
                att = cur.fetchone()

                if not att:
                    return jsonify({
                        "ok": True, "recognized": True,
                        "student": student_info,
                        "box": [int(x), int(y), int(w), int(h)],
                        "checked_out": False,
                        "message": "لا يوجد سجل حضور لهذا الطالب"
                    })

                if att["check_out"]:
                    return jsonify({
                        "ok": True, "recognized": True,
                        "student": student_info,
                        "box": [int(x), int(y), int(w), int(h)],
                        "checked_out": False,
                        "message": "تم تسجيل الانصراف مسبقًا"
                    })

                cur.execute("""
                    UPDATE attendance SET check_out = ? WHERE id = ?
                """, (now.isoformat(), att["id"]))
                conn.commit()

                return jsonify({
                    "ok": True, "recognized": True,
                    "student": student_info,
                    "box": [int(x), int(y), int(w), int(h)],
                    "checked_out": True
                })

            # ── وضع الحضور ──
            cur.execute("""
                SELECT id FROM attendance
                WHERE session_id = ? AND university_id = ?
                LIMIT 1
            """, (active_session_id, uid))
            existing = cur.fetchone()

            if existing:
                # لا تسجّل في الـ logs إذا سُجّل نفس الطالب خلال آخر 60 ثانية
                cache_key = (active_session_id, uid)
                now_ts = time.time()
                if cache_key not in _duplicate_cache or (now_ts - _duplicate_cache[cache_key]) > _DUPLICATE_COOLDOWN:
                    _duplicate_cache[cache_key] = now_ts
                    try:
                        log_admin_activity(uid, student_info["name"], "DUPLICATE_ATTENDANCE_ATTEMPT",
                            session_id=active_session_id, details="محاولة حضور مكررة")
                    except Exception:
                        pass
                return jsonify({
                    "ok": True, "recognized": True,
                    "student": student_info,
                    "box": [int(x), int(y), int(w), int(h)],
                    "new_record": False
                })

            # تحديد حالة الحضور (حاضر أو متأخر)
            try:
                start_h, start_m = map(int, session_row["start_time"].split(":"))
                session_start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                diff_minutes  = (now - session_start).total_seconds() / 60
                status = "Late" if diff_minutes > 15 else "Present"
            except Exception:
                status = "Present"

            cur.execute("""
                INSERT INTO attendance (session_id, university_id, check_in, status)
                VALUES (?, ?, ?, ?)
            """, (active_session_id, uid, now.isoformat(), status))
            conn.commit()

            log_admin_activity(
                uid,
                student_info["name"],
                "ATTENDANCE_MARKED",
                session_id=active_session_id,
                details=f"status={status},dist={min_dist:.3f},mode=kiosk"
            )

            return jsonify({
                "ok": True, "recognized": True,
                "student": dict(student_info, status=status),
                "box": [int(x), int(y), int(w), int(h)],
                "new_record": True
            })

        finally:
            if conn: conn.close()

