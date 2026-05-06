"""
anti_spoofing.py
================
Presentation Attack Detection (PAD) module for Smart Attendance System.

Methods implemented:
    1. Temporal Motion Analysis  — detects pixel-level motion across frames
    2. Texture Variance Analysis — distinguishes real skin from printed/screen surface
    3. Brightness Uniformity    — screens emit uniform light; real faces don't
    4. Edge Density Check       — printed images have sharper, denser edges

Usage:
    from anti_spoofing import AntiSpoofing

    detector = AntiSpoofing()
    result   = detector.check(frame_bgr)   # call on every captured frame
    if result.is_live:
        # proceed with face recognition
"""

import cv2
import numpy as np
from collections import deque
from dataclasses import dataclass


# ── Thresholds ────────────────────────────────────────────────────────────────

MOTION_THRESHOLD      = 12.0   # minimum average pixel motion required
MOTION_FRAMES         = 15    # number of frames to analyse for motion
TEXTURE_VAR_MIN       = 150.0  # real skin has higher local variance than paper/screen
BRIGHTNESS_UNIF_MAX   = 25.0   # screens are too uniform (low std-dev of brightness)
EDGE_DENSITY_MAX      = 0.15   # printed photos have dense sharp edges


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class SpoofResult:
    is_live:        bool
    score:          float   # 0.0 (spoof) → 1.0 (live)
    motion_ok:      bool
    texture_ok:     bool
    brightness_ok:  bool
    edge_ok:        bool
    reason:         str


# ── Main class ────────────────────────────────────────────────────────────────

class AntiSpoofing:
    """
    Multi-layer Presentation Attack Detector.

    Maintains a rolling buffer of recent frames to compute temporal features.
    Stateless per-frame checks (texture, brightness, edge) run on every call.
    """

    def __init__(self):
        self._frame_buffer: deque = deque(maxlen=MOTION_FRAMES)
        self._gray_buffer:  deque = deque(maxlen=MOTION_FRAMES)

    # ── Public API ────────────────────────────────────────────────────────────

    def check(self, frame_bgr: np.ndarray) -> SpoofResult:
        """
        Run all anti-spoofing checks on a single BGR frame.

        Parameters
        ----------
        frame_bgr : np.ndarray
            Full camera frame (BGR, any resolution).

        Returns
        -------
        SpoofResult
        """
        if frame_bgr is None or frame_bgr.size == 0:
            return self._fail("empty frame")

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

        # -- Layer 1: Temporal Motion --
        motion_ok, motion_score = self._check_motion(gray)

        # -- Layer 2: Texture Variance --
        texture_ok, texture_score = self._check_texture(gray)

        # -- Layer 3: Brightness Uniformity --
        brightness_ok, brightness_score = self._check_brightness(gray)

        # -- Layer 4: Edge Density --
        edge_ok, edge_score = self._check_edges(gray)

        # Update buffer after checks
        self._gray_buffer.append(gray.copy())

        # Weighted score (motion is most important)
        score = (
            motion_score     * 0.45 +
            texture_score    * 0.25 +
            brightness_score * 0.15 +
            edge_score       * 0.15
        )

        # Must pass motion + at least 2 of the other 3 checks
        static_pass = sum([texture_ok, brightness_ok, edge_ok]) >= 2
        is_live     = motion_ok and static_pass

        reason = "live" if is_live else self._reason(
            motion_ok, texture_ok, brightness_ok, edge_ok
        )

        return SpoofResult(
            is_live       = is_live,
            score         = round(score, 3),
            motion_ok     = motion_ok,
            texture_ok    = texture_ok,
            brightness_ok = brightness_ok,
            edge_ok       = edge_ok,
            reason        = reason
        )

    def reset(self):
        """Clear frame history (call when switching sessions)."""
        self._frame_buffer.clear()
        self._gray_buffer.clear()

    # ── Layer 1: Temporal Motion Analysis ────────────────────────────────────

    def _check_motion(self, gray: np.ndarray):
        """
        Computes mean absolute difference between consecutive frames.
        A real face naturally moves (breathing, micro-movements).
        A static photo has near-zero motion.
        """
        if len(self._gray_buffer) < 3:
            # Not enough frames yet — neutral score, don't block
            return True, 0.5

        diffs = []
        buf = list(self._gray_buffer)
        for i in range(1, len(buf)):
            diff = cv2.absdiff(buf[i], buf[i - 1])
            diffs.append(float(np.mean(diff)))

        avg_motion = float(np.mean(diffs))
        ok    = avg_motion >= MOTION_THRESHOLD
        score = min(avg_motion / (MOTION_THRESHOLD * 2), 1.0)
        return ok, score

    # ── Layer 2: Texture Variance Analysis ───────────────────────────────────

    def _check_texture(self, gray: np.ndarray):
        """
        Real skin has complex micro-texture (pores, fine hairs).
        Printed paper or screens have more uniform, low-variance texture.
        Uses local standard deviation via a small window.
        """
        resized = cv2.resize(gray, (64, 64))
        kernel  = np.ones((5, 5), np.float32) / 25
        mean    = cv2.filter2D(resized.astype(np.float32), -1, kernel)
        sq_mean = cv2.filter2D((resized.astype(np.float32)) ** 2, -1, kernel)
        local_var = np.sqrt(np.maximum(sq_mean - mean ** 2, 0))
        avg_var = float(np.mean(local_var))
        ok    = avg_var >= TEXTURE_VAR_MIN
        score = min(avg_var / (TEXTURE_VAR_MIN * 1.5), 1.0)
        return ok, score

    # ── Layer 3: Brightness Uniformity ───────────────────────────────────────

    def _check_brightness(self, gray: np.ndarray):
        """
        Screens emit very uniform light across all pixels.
        Real faces have natural shadows and highlights (non-uniform brightness).
        A low standard deviation of brightness → likely a screen.
        """
        std = float(np.std(gray.astype(np.float32)))
        ok    = std >= BRIGHTNESS_UNIF_MAX
        score = min(std / (BRIGHTNESS_UNIF_MAX * 3), 1.0)
        return ok, score

    # ── Layer 4: Edge Density ─────────────────────────────────────────────────

    def _check_edges(self, gray: np.ndarray):
        """
        Printed photos and phone screens tend to have sharper, denser edges
        due to re-digitisation artefacts (moiré, JPEG compression).
        A very high edge density indicates a 2-D presentation attack.
        """
        resized = cv2.resize(gray, (128, 128))
        edges   = cv2.Canny(resized, 50, 150)
        density = float(np.count_nonzero(edges)) / edges.size
        ok      = density <= EDGE_DENSITY_MAX
        score   = max(1.0 - density / EDGE_DENSITY_MAX, 0.0)
        return ok, score

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _fail(reason: str) -> SpoofResult:
        return SpoofResult(
            is_live       = False,
            score         = 0.0,
            motion_ok     = False,
            texture_ok    = False,
            brightness_ok = False,
            edge_ok       = False,
            reason        = reason
        )

    @staticmethod
    def _reason(motion, texture, brightness, edge) -> str:
        if not motion:
            return "no_motion — static image or photo detected"
        failed = []
        if not texture:    failed.append("low_texture")
        if not brightness: failed.append("uniform_brightness (screen)")
        if not edge:       failed.append("high_edge_density (print/screen)")
        return " | ".join(failed) or "spoof_detected"
