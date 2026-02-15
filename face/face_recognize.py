import cv2
import numpy as np
import os
from facenet_model import get_embedding

EMB_DIR = "data/embeddings"
THRESHOLD = 0.95  # جرّب 0.9 - 1.1 حسب بياناتك

def load_embeddings():
    data = {}
    for file in os.listdir(EMB_DIR):
        if file.endswith(".npy"):
            student_id = file.replace("student_", "").replace(".npy", "")
            data[int(student_id)] = np.load(os.path.join(EMB_DIR, file))
    return data

embeddings = load_embeddings()
print("✅ Loaded embeddings:", list(embeddings.keys()))

cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

frame_count = 0
last_result = None

# ✅ نخلي التعرف يتحدث كل N فريم بدل كل فريم
RECOGNIZE_EVERY = 10   # جرّب 5 أو 10 أو 15 (كلما زاد أسرع لكن تحديث أقل)
cached_result = "..."

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    frame_count += 1

    # ✅ اعمل التعرف كل N فريم فقط
    if frame_count % RECOGNIZE_EVERY == 0:
        # تصغير خفيف قبل MTCNN (يساعد سرعة الكشف)
        small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)

        # مهم: تحويل BGR → RGB (يحسن اكتشاف الوجه)
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)

        emb = get_embedding(rgb)  # get_embedding عندك يستخدم MTCNN

        if emb is None:
            cached_result = "❌ Unknown Face"
        else:
            matched_id = None
            min_dist = 999

            for sid, db_emb in embeddings.items():
                dist = np.linalg.norm(emb - db_emb)
                if dist < min_dist:
                    min_dist = dist
                    matched_id = sid

            if min_dist < THRESHOLD:
                cached_result = f"✅ Student Recognized: ID = {matched_id}"
            else:
                cached_result = "❌ Unknown Face"

        # اطبع فقط إذا تغيرت النتيجة
        if cached_result != last_result:
            print(cached_result)
            last_result = cached_result

    # ✅ عرض النتيجة المتخزنة على الفيديو (فوري)
    cv2.putText(frame, cached_result, (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("Recognition", frame)
    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()
