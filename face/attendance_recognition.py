import cv2
import time
from datetime import datetime

from face.facenet_model import get_embedding
from face.face_utils import load_embeddings, recognize_face
from db.attendance_db import (
    has_open_attendance,
    check_in,
    check_out_all_section
)

# =========================
# CONFIG
# =========================
CAMERA_INDEX = 0
SESSION_DURATION = 60      # مدة الحصة (ثواني – للتجربة)
CHECK_INTERVAL = 2         # كل كم ثانية نتحقق


def start_attendance(section_id):
    print(f"📷 Attendance started | Section {section_id}")

    db_embeddings = load_embeddings()
    if not db_embeddings:
        print("❌ No student embeddings found")
        return

    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("❌ Camera not accessible")
        return

    start_time = time.time()
    last_seen = {}

    while True:
        ret, frame = cap.read()
        if not ret:
            continue

        emb = get_embedding(frame)
        student_id = recognize_face(emb, db_embeddings)

        now = time.time()

        if student_id:
            # منع التكرار السريع
            if student_id not in last_seen or now - last_seen[student_id] > 10:
                if not has_open_attendance(student_id, section_id):
                    check_in(student_id, section_id)
                    print(f"✅ Check-in: Student {student_id}")

                last_seen[student_id] = now

        cv2.imshow("FaceNet Attendance", frame)

        # انتهاء الحصة
        if time.time() - start_time > SESSION_DURATION:
            print("⏹ Session ended automatically")
            break

        # خروج يدوي
        if cv2.waitKey(1) & 0xFF == 27:
            print("⛔ Session stopped manually")
            break

        time.sleep(CHECK_INTERVAL)

    # تسجيل الانصراف للجميع
    check_out_all_section(section_id)

    cap.release()
    cv2.destroyAllWindows()
    print("📊 Attendance saved successfully")
