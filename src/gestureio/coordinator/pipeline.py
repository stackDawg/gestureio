"""Camera -> mirror -> models -> features, one frame at a time.

This is the only place frames are mirrored. Everything downstream (inference,
features, preview, recordings) sees the selfie view: the user's right hand is on
the right of the image, and MediaPipe labels it "Right".
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from gestureio.coordinator.features import HandFeatures, PoseThresholds, hand_features
from gestureio.coordinator.types import TrackedFace, TrackedHand


@dataclass(frozen=True)
class FrameResult:
    seq: int
    t_capture: float  # monotonic time the camera read returned
    t_done: float  # monotonic time features were ready
    image: np.ndarray  # mirrored BGR frame
    hands: list[TrackedHand]
    features: list[HandFeatures]
    faces: list[TrackedFace] | None  # None when face detection didn't run on this frame
    hand_ms: float
    face_ms: float | None


class Pipeline:
    def __init__(self, capture, hands, faces=None, *, active_fps: float = 30.0,
                 idle_fps: float = 8.0, idle_after_s: float = 2.0, face_interval_s: float = 0.5,
                 max_width: int | None = 640, thresholds: PoseThresholds = PoseThresholds()):
        self.capture, self.hands, self.faces = capture, hands, faces
        self.max_width = max_width
        self.active_fps, self.idle_fps, self.idle_after_s = active_fps, idle_fps, idle_after_s
        self.face_interval_s = face_interval_s
        self.thresholds = thresholds
        self._seq = 0
        self._last_t = float("-inf")  # capture time of the last processed frame
        self._last_hand_t = float("-inf")
        self._last_face_t = float("-inf")

    @property
    def idle(self) -> bool:
        """No hand seen recently, so frames are processed at the lower idle rate."""
        if self._last_hand_t == float("-inf"):
            return True
        return self._last_t - self._last_hand_t > self.idle_after_s

    def next(self, timeout: float = 1.0) -> FrameResult | None:
        """Process the next frame due under the current rate; None if the camera went quiet."""
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            frame = self.capture.latest(self._seq, remaining)
            if frame is None:
                return None
            self._seq = frame.seq
            interval = 1.0 / (self.idle_fps if self.idle else self.active_fps)
            # 10% slack so camera jitter doesn't skip frames that are due.
            if frame.t - self._last_t >= 0.9 * interval:
                break

        self._last_t = frame.t
        image = frame.image
        # Cameras sometimes ignore the requested size. MediaPipe shrinks frames to
        # its model input anyway, so shrinking first only saves work.
        if self.max_width and image.shape[1] > self.max_width:
            height = round(image.shape[0] * self.max_width / image.shape[1])
            image = cv2.resize(image, (self.max_width, height), interpolation=cv2.INTER_AREA)
        image = cv2.flip(image, 1)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        t0 = time.perf_counter()
        hands = self.hands.detect(rgb, frame.t)
        t1 = time.perf_counter()
        faces, face_ms = None, None
        if self.faces is not None and frame.t - self._last_face_t >= self.face_interval_s:
            faces = self.faces.detect(rgb, frame.t)
            face_ms = (time.perf_counter() - t1) * 1000.0
            self._last_face_t = frame.t
        if hands:
            self._last_hand_t = frame.t

        size = (image.shape[1], image.shape[0])
        features = [hand_features(h.image_lm, h.world_lm, h.handedness, h.score, size,
                                  self.thresholds) for h in hands]
        return FrameResult(frame.seq, frame.t, time.monotonic(), image, hands, features, faces,
                           (t1 - t0) * 1000.0, face_ms)

    def close(self) -> None:
        self.capture.stop()
        self.hands.close()
        if self.faces is not None:
            self.faces.close()
