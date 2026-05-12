from keras_facenet import FaceNet
import numpy as np

# تحميل نموذج FaceNet مرة وحدة
embedder = FaceNet()

def get_face_embedding(face_image):
    """
    Takes a face image (numpy array) and returns FaceNet embedding
    """
    face_image = face_image.astype("float32")

    # FaceNet expects shape (160, 160, 3)
    if face_image.shape[0] != 160 or face_image.shape[1] != 160:
        import cv2
        face_image = cv2.resize(face_image, (160, 160))

    embedding = embedder.embeddings([face_image])
    return embedding[0]
