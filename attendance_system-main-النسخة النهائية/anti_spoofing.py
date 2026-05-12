"""
anti_spoofing.py — V9 BLINK-CENTRIC
=====================================
المنطق المبسّط والفعّال:

- blink_detected = True  → live ✅ (الوجه الحقيقي يرمش)
- blink_detected = False → spoof ❌ (الصورة لا ترمش)

الاختبارات الثابتة موجودة للـ logging والتقديم فقط.
"""

import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class SpoofResult:
    is_live:    bool
    score:      float
    reason:     str
    blink_ok:   bool = False
    skin_ok:    bool = False
    wrinkle_ok: bool = False
    pore_ok:    bool = False
    color_ok:   bool = False


class AntiSpoofing:

    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    def check(self, frame_bgr, blink_detected=False, room_id="default"):
        """
        المنطق: blink_detected هو الفاصل
        - blink = True  → live
        - blink = False → spoof
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return self._fail("empty")

        try:
            h, w = frame_bgr.shape[:2]
            scale = min(1.0, 400 / max(w, h))
            img = cv2.resize(frame_bgr, (int(w*scale), int(h*scale)))
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            faces = self.face_cascade.detectMultiScale(gray, 1.2, 5, minSize=(80, 80))
            if len(faces) == 0:
                return self._fail("no_face")

            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            face_gray = gray[y:y+fh, x:x+fw]
            face_bgr  = img[y:y+fh, x:x+fw]

            # الاختبارات الثابتة (للـ logging)
            skin_ok,    skin_score    = self._check_skin_surface(face_bgr)
            wrinkle_ok, wrinkle_score = self._check_wrinkles(face_gray)
            pore_ok,    pore_score    = self._check_pores(face_gray)
            color_ok,   color_score   = self._check_color_tone(face_bgr)

            score = (
                (1.0 if blink_detected else 0.0) * 0.60 +
                skin_score    * 0.10 +
                wrinkle_score * 0.10 +
                pore_score    * 0.10 +
                color_score   * 0.10
            )

            # القرار البسيط: blink فقط
            is_live = blink_detected

            if is_live:
                reason = f"live(blink=YES,skin={skin_ok},wrinkle={wrinkle_ok},pore={pore_ok},color={color_ok})"
            else:
                reason = f"spoof(no_blink,skin={skin_ok},wrinkle={wrinkle_ok},pore={pore_ok},color={color_ok})"

            return SpoofResult(
                is_live=is_live, score=round(score, 3), reason=reason,
                blink_ok=blink_detected,
                skin_ok=skin_ok, wrinkle_ok=wrinkle_ok,
                pore_ok=pore_ok, color_ok=color_ok,
            )

        except Exception as e:
            return self._fail(f"err:{e}")

    def reset(self, room_id=None):
        pass

    def _check_skin_surface(self, face_bgr):
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
        kernel = np.ones((5, 5), np.float32) / 25
        mean = cv2.filter2D(gray.astype(np.float32), -1, kernel)
        sq   = cv2.filter2D((gray.astype(np.float32))**2, -1, kernel)
        local_var = np.sqrt(np.maximum(sq - mean**2, 0))
        avg_var = float(local_var.mean())
        ok = avg_var > 7.0
        score = min(avg_var / 15.0, 1.0)
        return ok, score

    def _check_wrinkles(self, face_gray):
        kernel = cv2.getGaborKernel((9, 9), 2.5, 0, 6.0, 0.5, 0, ktype=cv2.CV_32F)
        filtered = cv2.filter2D(face_gray, cv2.CV_32F, kernel)
        response = np.abs(filtered)
        strong_ratio = float((response > 30).sum()) / response.size
        ok = 0.03 < strong_ratio < 0.35
        score = 1.0 if ok else max(0, 1 - abs(strong_ratio - 0.15) * 5)
        return ok, score

    def _check_pores(self, face_gray):
        blur = cv2.GaussianBlur(face_gray, (7, 7), 0)
        high_pass = cv2.absdiff(face_gray, blur)
        detail_count = (high_pass > 8).sum()
        ratio = float(detail_count) / face_gray.size
        ok = 0.08 < ratio < 0.50
        score = 1.0 if ok else max(0, 1 - abs(ratio - 0.25) * 3)
        return ok, score

    def _check_color_tone(self, face_bgr):
        ycrcb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2YCrCb)
        cr = ycrcb[:,:,1]
        cb = ycrcb[:,:,2]
        skin_mask = (cr >= 130) & (cr <= 180) & (cb >= 80) & (cb <= 140)
        skin_ratio = float(skin_mask.sum()) / skin_mask.size
        ok = skin_ratio > 0.30
        score = min(skin_ratio / 0.50, 1.0)
        return ok, score

    @staticmethod
    def _fail(reason):
        return SpoofResult(False, 0.0, reason)
