"""Tracker outputs, kept free of MediaPipe imports so recordings load without it."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TrackedHand:
    image_lm: np.ndarray  # (21, 3) normalised image coords of the mirrored frame
    world_lm: np.ndarray | None  # (21, 3) metres, hand-centred
    handedness: str  # "Left" or "Right": the user's real hand
    score: float


@dataclass(frozen=True)
class TrackedFace:
    box: tuple[float, float, float, float]  # x, y, w, h, normalised
    score: float
