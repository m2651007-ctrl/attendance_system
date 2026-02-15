import torch
import numpy as np
from facenet_pytorch import MTCNN, InceptionResnetV1

# =========================
# DEVICE
# =========================
device = "cuda" if torch.cuda.is_available() else "cpu"

# =========================
# FACE DETECTOR
# =========================
mtcnn = MTCNN(
    image_size=160,
    margin=20,
    min_face_size=40,
    thresholds=[0.6, 0.7, 0.7],
    device=device
)

# =========================
# FACENET MODEL
# =========================
model = InceptionResnetV1(
    pretrained="vggface2"
).eval().to(device)


# =========================
# GET EMBEDDING
# =========================
def get_embedding(frame):
    """
    frame: OpenCV frame (BGR)
    return: 512-d embedding or None
    """

    # Detect + align face
    face = mtcnn(frame)

    if face is None:
        return None  # ❌ لا يوجد وجه

    # Add batch dim
    face = face.unsqueeze(0).to(device)

    with torch.no_grad():
        embedding = model(face)

    return embedding.cpu().numpy()[0]
