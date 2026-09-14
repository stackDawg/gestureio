"""Loads the real MediaPipe models; skipped until tools/fetch_models.py has run."""

import numpy as np
import pytest

from gestureio.common.paths import MODELS_DIR

pytestmark = pytest.mark.skipif(
    not (MODELS_DIR / "hand_landmarker.task").exists()
    or not (MODELS_DIR / "blaze_face_short_range.tflite").exists(),
    reason="models not downloaded; run tools/fetch_models.py",
)


def test_blank_frame_has_no_hands_or_faces():
    from gestureio.coordinator.tracker import FaceTracker, HandTracker

    rgb = np.zeros((480, 640, 3), np.uint8)
    with HandTracker() as hands, FaceTracker() as faces:
        assert hands.detect(rgb, 1.0) == []
        assert hands.detect(rgb, 1.0) == []  # a repeated timestamp must not break VIDEO mode
        assert faces.detect(rgb, 1.0) == []
