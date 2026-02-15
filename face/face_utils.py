import numpy as np
import os

# =========================
# CONFIG
# =========================
EMB_DIR = "data/embeddings"
THRESHOLD = 0.7   # أفضل قيمة لـ FaceNet


# =========================
# LOAD ALL EMBEDDINGS
# =========================
def load_embeddings():
    """
    Loads all saved face embeddings from disk.
    File format: student_<id>.npy
    """
    embeddings = {}

    if not os.path.exists(EMB_DIR):
        print("⚠️ Embedding directory not found")
        return embeddings

    for file in os.listdir(EMB_DIR):
        if file.startswith("student_") and file.endswith(".npy"):
            try:
                student_id = int(
                    file.replace("student_", "").replace(".npy", "")
                )
                embeddings[student_id] = np.load(
                    os.path.join(EMB_DIR, file)
                )
            except Exception as e:
                print(f"❌ Error loading {file}: {e}")

    return embeddings


# =========================
# FACE RECOGNITION
# =========================
def recognize_face(embedding, db_embeddings):
    """
    Compare a face embedding with stored embeddings.
    Returns student_id if matched, otherwise None.
    """
    if embedding is None:
        return None

    if not db_embeddings:
        return None

    best_id = None
    best_distance = float("inf")

    for student_id, stored_embedding in db_embeddings.items():
        distance = np.linalg.norm(embedding - stored_embedding)

        if distance < best_distance:
            best_distance = distance
            best_id = student_id

    if best_distance < THRESHOLD:
        return best_id

    return None
