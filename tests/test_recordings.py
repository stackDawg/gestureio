"""Pose recognition on real recordings from the laptop (recordings/*.jsonl).

This is the regression net for threshold changes. Each case matches what was
performed in front of the camera.
"""

import collections

import pytest

from gestureio.common.paths import RECORDINGS_DIR
from gestureio.coordinator.features import hand_features
from gestureio.coordinator.recording import pose_timeline, read_recording

CASES = [  # label, hand, expected pose, minimum share of that hand's frames
    ("right-palm", "Right", "palm", 0.95),
    ("left-palm", "Left", "palm", 0.95),
    ("right-count1", "Right", "count1", 0.95),
    ("right-count2", "Right", "count2", 0.95),
    ("right-count3", "Right", "count3", 0.95),
    ("right-count4", "Right", "count4", 0.95),
    ("left-count2", "Left", "count2", 0.95),
    ("right-fist", "Right", "fist", 0.95),
    ("right-pinch", "Right", "pinch", 0.90),
    ("two-hands", "Right", "palm", 0.90),
    ("two-hands", "Left", "palm", 0.90),
]


def _load(label: str):
    paths = sorted(RECORDINGS_DIR.glob(f"{label}-2*.jsonl"))
    if not paths:
        pytest.skip(f"no {label} recording")
    header, frames = read_recording(paths[-1])
    return tuple(header["frame_size"]), frames


def _poses(label: str, hand: str) -> list[str]:
    size, frames = _load(label)
    return [hand_features(h.image_lm, h.world_lm, h.handedness, h.score, size).pose
            for f in frames for h in f.hands if h.handedness == hand]


@pytest.mark.parametrize("label, hand, pose, min_share", CASES)
def test_recorded_pose_is_recognised(label, hand, pose, min_share):
    poses = _poses(label, hand)
    counts = collections.Counter(poses)
    assert counts[pose] / len(poses) >= min_share, counts.most_common(4)


def test_fist_never_holds_a_pinch():
    # The recording's first frame catches the hand still closing (index 0.73) and
    # reads as pinch. One frame is harmless, because every pinch mode needs the pinch
    # to last. A sustained misread would not be.
    size, frames = _load("right-fist")
    runs = [s for s in pose_timeline(frames, size) if s.pose == "pinch"]
    assert all(s.duration < 0.15 for s in runs), runs
