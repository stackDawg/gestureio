"""Geometric features of one tracked hand.

Finger straightness and thumb position use MediaPipe's world landmarks. Those are
metric and centred on the hand, so they don't change with distance from the
camera or with hand rotation. Pinch, position and angle use image landmarks
converted to pixels: in the laptop recordings, world-landmark depth was too noisy
for pinch (a held pinch read anywhere from 0.21 to 0.72), while the image-plane
ratio stayed at 0.17-0.24.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

WRIST = 0
THUMB_TIP = 4
INDEX_MCP = 5
MIDDLE_MCP = 9
PINKY_MCP = 17
INDEX_TIP = 8
PALM_POINTS = [0, 5, 9, 13, 17]

# MCP, PIP, DIP, TIP for each non-thumb finger.
FINGERS: dict[str, tuple[int, int, int, int]] = {
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}

EXT, MID, FOLD = "ext", "mid", "fold"


@dataclass(frozen=True)
class PoseThresholds:
    finger_ext: float = 0.85  # straightness at or above this: extended
    finger_fold: float = 0.70  # at or below this: folded; in between: ambiguous
    # Thumb tip to middle MCP, over palm length. Recorded counts: 0.41-0.57; palms: 0.75+.
    thumb_out: float = 0.75
    thumb_in: float = 0.65
    # Thumb tip to index tip over palm length, in the image plane. Held pinch: 0.17-0.24.
    pinch_on: float = 0.30
    pinch_off: float = 0.45  # used by the arbiter's hysteresis, not here
    # A fist also brings thumb and index tips together; its index is folded (0.46-0.50),
    # a pinching index is not (0.73-0.84).
    pinch_index_min: float = 0.62


@dataclass(frozen=True)
class HandFeatures:
    handedness: str  # "Left" or "Right": the user's real hand
    handedness_score: float
    straightness: dict[str, float]
    fingers: dict[str, str]  # EXT / MID / FOLD per non-thumb finger
    thumb_ratio: float
    thumb: str  # EXT / MID / FOLD
    pinch_ratio: float
    pose: str  # palm, fist, pinch, L, count1..count4, other
    knuckle_deg: float  # image-plane angle of the index MCP -> pinky MCP line
    center: tuple[float, float]  # palm centre, normalised image coords
    bbox_area: float  # landmark bounding box as a fraction of the frame

    @property
    def extended_count(self) -> int:
        return sum(state == EXT for state in self.fingers.values())


def straightness(points: np.ndarray, chain: tuple[int, ...]) -> float:
    """Wrist-to-tip distance over the length of the joint chain; 1.0 is a straight finger."""
    pts = points[[WRIST, *chain]]
    chain_len = float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())
    if chain_len == 0.0:
        return 0.0
    return float(np.linalg.norm(pts[-1] - pts[0]) / chain_len)


def _tristate(value: float, high: float, low: float) -> str:
    if value >= high:
        return EXT
    if value <= low:
        return FOLD
    return MID


def classify_pose(fingers: dict[str, str], straight: dict[str, float], thumb: str,
                  pinch_ratio: float, th: PoseThresholds) -> str:
    if pinch_ratio < th.pinch_on and straight["index"] >= th.pinch_index_min:
        return "pinch"
    states = list(fingers.values())
    # An ambiguous finger makes every count and pose unreliable, so refuse to guess.
    if MID in states:
        return "other"
    n = states.count(EXT)
    if n == 4 and thumb == EXT:
        return "palm"
    if n == 0 and thumb != EXT:
        return "fist"
    if n == 1 and fingers["index"] == EXT and thumb == EXT:
        return "L"
    # Counting needs a clearly folded thumb; that margin keeps count4 apart from palm.
    if 1 <= n <= 4 and thumb == FOLD:
        return f"count{n}"
    return "other"


def angle_delta_deg(a: float, b: float) -> float:
    """Signed smallest rotation from angle b to angle a, in (-180, 180]."""
    d = (a - b) % 360.0
    return d - 360.0 if d > 180.0 else d


def hand_features(image_lm: np.ndarray, world_lm: np.ndarray | None, handedness: str,
                  handedness_score: float, frame_size: tuple[int, int],
                  th: PoseThresholds = PoseThresholds()) -> HandFeatures:
    """Compute features from (21, 3) image landmarks (normalised) and world landmarks (metres)."""
    w, h = frame_size
    px = image_lm[:, :2] * (w, h)
    if world_lm is not None:
        pose_pts = world_lm
    else:
        # MediaPipe's image z is on roughly the same scale as x.
        pose_pts = np.column_stack([px, image_lm[:, 2] * w])

    palm = max(float(np.linalg.norm(pose_pts[MIDDLE_MCP] - pose_pts[WRIST])), 1e-9)
    straight = {name: straightness(pose_pts, chain) for name, chain in FINGERS.items()}
    fingers = {name: _tristate(v, th.finger_ext, th.finger_fold) for name, v in straight.items()}
    thumb_ratio = float(np.linalg.norm(pose_pts[THUMB_TIP] - pose_pts[MIDDLE_MCP])) / palm
    thumb = _tristate(thumb_ratio, th.thumb_out, th.thumb_in)
    palm_px = max(float(np.linalg.norm(px[MIDDLE_MCP] - px[WRIST])), 1e-9)
    pinch_ratio = float(np.linalg.norm(px[THUMB_TIP] - px[INDEX_TIP])) / palm_px

    d = px[PINKY_MCP] - px[INDEX_MCP]
    knuckle_deg = math.degrees(math.atan2(d[1], d[0]))
    cx, cy = image_lm[PALM_POINTS, :2].mean(axis=0)
    span = image_lm[:, :2].max(axis=0) - image_lm[:, :2].min(axis=0)

    return HandFeatures(
        handedness=handedness,
        handedness_score=handedness_score,
        straightness=straight,
        fingers=fingers,
        thumb_ratio=thumb_ratio,
        thumb=thumb,
        pinch_ratio=pinch_ratio,
        pose=classify_pose(fingers, straight, thumb, pinch_ratio, th),
        knuckle_deg=knuckle_deg,
        center=(float(cx), float(cy)),
        bbox_area=float(span[0] * span[1]),
    )
