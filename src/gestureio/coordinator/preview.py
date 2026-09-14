"""Drawing for the debug preview: hand skeletons, per-hand readouts, and a HUD."""

from __future__ import annotations

import cv2
import numpy as np

from gestureio.coordinator.features import EXT, FOLD, HandFeatures
from gestureio.coordinator.types import TrackedFace

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
)

# BGR
WHITE = (255, 255, 255)
GREY = (150, 150, 150)
GREEN = (80, 200, 80)
RED = (60, 60, 230)
AMBER = (0, 180, 255)
HAND_COLORS = {"Right": (0, 140, 255), "Left": (230, 190, 0)}
FONT = cv2.FONT_HERSHEY_SIMPLEX
_STATE_MARK = {EXT: "+", FOLD: "-"}


def text(img, s: str, org, color=WHITE, scale: float = 0.5, thickness: int = 1) -> None:
    cv2.putText(img, s, org, FONT, scale, (0, 0, 0), thickness + 2, cv2.LINE_AA)
    cv2.putText(img, s, org, FONT, scale, color, thickness, cv2.LINE_AA)


def draw_hand(img: np.ndarray, image_lm: np.ndarray, feat: HandFeatures) -> None:
    h, w = img.shape[:2]
    pts = [tuple(p) for p in (image_lm[:, :2] * (w, h)).astype(int)]
    color = HAND_COLORS.get(feat.handedness, GREY)
    for a, b in HAND_CONNECTIONS:
        cv2.line(img, pts[a], pts[b], color, 2, cv2.LINE_AA)
    for p in pts:
        cv2.circle(img, p, 3, WHITE, -1, cv2.LINE_AA)

    x = int(np.clip(pts[0][0] - 70, 4, w - 230))
    y = int(np.clip(pts[0][1] + 24, 20, h - 44))
    marks = " ".join(f"{name[0]}{_STATE_MARK.get(state, '~')}" for name, state in
                     [("thumb", feat.thumb), *feat.fingers.items()])
    text(img, f"{feat.handedness.upper()} {feat.handedness_score:.2f}  {feat.pose}", (x, y), color, 0.6, 2)
    text(img, f"{marks}   thumb {feat.thumb_ratio:.2f}", (x, y + 18), WHITE, 0.45)
    text(img, f"pinch {feat.pinch_ratio:.2f}  knuckle {feat.knuckle_deg:+.0f}  area {feat.bbox_area:.3f}",
         (x, y + 36), WHITE, 0.45)


def draw_faces(img: np.ndarray, faces: list[TrackedFace]) -> None:
    h, w = img.shape[:2]
    for f in faces:
        x, y, bw, bh = f.box
        p1, p2 = (int(x * w), int(y * h)), (int((x + bw) * w), int((y + bh) * h))
        cv2.rectangle(img, p1, p2, GREEN, 1, cv2.LINE_AA)
        text(img, f"face {f.score:.2f}", (p1[0], max(p1[1] - 6, 12)), GREEN, 0.45)


def draw_hud(img: np.ndarray, lines: list[tuple[str, tuple]]) -> None:
    """Lines of (text, colour) top-left, over a darkened panel."""
    if not lines:
        return
    height = 12 + 18 * len(lines)
    width = min(img.shape[1], 12 + max(cv2.getTextSize(s, FONT, 0.45, 1)[0][0] for s, _ in lines))
    panel = img[:height, :width]
    panel[:] = (panel * 0.35).astype(np.uint8)
    for i, (s, color) in enumerate(lines):
        text(img, s, (6, 20 + 18 * i), color, 0.45)


def draw_banner(img: np.ndarray, s: str, color=WHITE, scale: float = 0.9) -> None:
    (tw, th), _ = cv2.getTextSize(s, FONT, scale, 2)
    h, w = img.shape[:2]
    text(img, s, ((w - tw) // 2, h - 24), color, scale, 2)
