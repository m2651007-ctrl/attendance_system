import cv2
import numpy as np
import os
from face.face_model import get_embedding  # تأكد من المسار الصحيح

# =========================
# CONFIG
# =========================
STUDENT_ID = 1            # لاحقًا من DB
SAVE_DIR = "data/embeddings"
CAMERA_INDEX = 0

os.makedirs(SAVE_DIR, exist_ok=True)

# =========================
# CAMERA
# =========================
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)

if not cap.isOpened():
    raise RuntimeError("❌ لم يتم العثور على كاميرا")

print("📸 اضغط [S] لحفظ بصمة الوجه")
print("❌ اضغط [Q] للخروج")

saved = False

# =========================
# LOOP
# =========================
while True:
    ret, frame = cap.read()
    if not ret:
        continue

    cv2.imshow("Register Face - Press S", frame)

    key = cv2.waitKey(1) & 0xFF

    # ---------- SAVE ----------
    if key == ord("s"):
        embedding = get_embedding(frame)

        if embedding is None:
            print("⚠️ لم يتم اكتشاف وجه، حاول مرة أخرى")
            continue

        path = os.path.join(SAVE_DIR, f"student_{STUDENT_ID}.npy")
        np.save(path, embedding)

        print(f"✅ تم حفظ بصمة الوجه بنجاح: {path}")
        saved = True
        break

    # ---------- EXIT ----------
    elif key == ord("q"):
        print("❌ تم الإلغاء")
        break

# =========================
# CLEANUP
# =========================
cap.release()
cv2.destroyAllWindows()

if saved:
    print("🎉 التسجيل اكتمل بنجاح")
else:
    print("⚠️ لم يتم حفظ أي بصمة")
