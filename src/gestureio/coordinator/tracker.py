"""MediaPipe hand and face models behind a small interface.

Input must already be mirrored (selfie view). MediaPipe's docs say its
handedness label assumes mirrored input, but on the laptop bench (mediapipe
1.0.1, 2026-09-14) mirrored frames came back labelled with the opposite hand.
user_hand() corrects that, so TrackedHand.handedness is the user's real hand.
"""

from __future__ import annotations

import os

# MediaPipe's native logging prints several harmless warnings per model load.
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

from pathlib import Path

import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from gestureio.common.paths import MODELS_DIR
from gestureio.coordinator.types import TrackedFace, TrackedHand

HAND_MODEL = MODELS_DIR / "hand_landmarker.task"
FACE_MODEL = MODELS_DIR / "blaze_face_short_range.tflite"
_SWAP = {"Left": "Right", "Right": "Left"}
# The handedness convention below was measured on this version. After upgrading
# MediaPipe, redo the bench right/left check before changing this.
VERIFIED_MEDIAPIPE = "1.0.1"


def user_hand(raw_label: str, invert: bool = False) -> str:
    """The user's real hand, given MediaPipe's label for a mirrored frame.

    `invert` flips the result again, for a camera that fails the first-run check.
    """
    label = _SWAP.get(raw_label, raw_label)
    return _SWAP.get(label, label) if invert else label


def _base_options(path: Path) -> mp_python.BaseOptions:
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing; run: uv run python tools/fetch_models.py")
    return mp_python.BaseOptions(model_asset_path=str(path))


class _VideoClock:
    """VIDEO mode requires strictly increasing millisecond timestamps."""

    def __init__(self):
        self._last = -1

    def __call__(self, t: float) -> int:
        self._last = max(int(t * 1000.0), self._last + 1)
        return self._last


class HandTracker:
    def __init__(self, num_hands: int = 2, min_detection: float = 0.5, min_presence: float = 0.5,
                 min_tracking: float = 0.5, invert_handedness: bool = False):
        options = vision.HandLandmarkerOptions(
            base_options=_base_options(HAND_MODEL),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=num_hands,
            min_hand_detection_confidence=min_detection,
            min_hand_presence_confidence=min_presence,
            min_tracking_confidence=min_tracking,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)
        self._clock = _VideoClock()
        self.invert_handedness = invert_handedness

    def detect(self, rgb: np.ndarray, t: float) -> list[TrackedHand]:
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect_for_video(image, self._clock(t))
        hands = []
        for img, world, cats in zip(result.hand_landmarks, result.hand_world_landmarks,
                                    result.handedness):
            hands.append(TrackedHand(
                image_lm=np.array([(p.x, p.y, p.z) for p in img], dtype=np.float64),
                world_lm=np.array([(p.x, p.y, p.z) for p in world], dtype=np.float64),
                handedness=user_hand(cats[0].category_name, self.invert_handedness),
                score=float(cats[0].score),
            ))
        return hands

    def close(self) -> None:
        self._landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FaceTracker:
    def __init__(self, min_detection: float = 0.5):
        options = vision.FaceDetectorOptions(
            base_options=_base_options(FACE_MODEL),
            running_mode=vision.RunningMode.VIDEO,
            min_detection_confidence=min_detection,
        )
        self._detector = vision.FaceDetector.create_from_options(options)
        self._clock = _VideoClock()

    def detect(self, rgb: np.ndarray, t: float) -> list[TrackedFace]:
        h, w = rgb.shape[:2]
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._detector.detect_for_video(image, self._clock(t))
        faces = []
        for det in result.detections:
            b = det.bounding_box
            score = det.categories[0].score if det.categories else 0.0
            faces.append(TrackedFace((b.origin_x / w, b.origin_y / h, b.width / w, b.height / h),
                                     float(score)))
        return faces

    def close(self) -> None:
        self._detector.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
