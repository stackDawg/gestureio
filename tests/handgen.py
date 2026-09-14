"""Synthetic MediaPipe-style hands for tests.

World landmarks in metres, wrist at the origin, fingers pointing +y, and curling
toward +z (the palm side). Only distances matter to the pose features, so the
exact frame is arbitrary.
"""

from __future__ import annotations

import math

import numpy as np

_MCP = {"index": (-0.030, 0.085), "middle": (-0.010, 0.090), "ring": (0.010, 0.087),
        "pinky": (0.028, 0.080)}
_SEGMENTS = {"index": (0.045, 0.025, 0.022), "middle": (0.050, 0.030, 0.024),
             "ring": (0.047, 0.028, 0.023), "pinky": (0.036, 0.021, 0.020)}
_INDICES = {"index": (5, 6, 7, 8), "middle": (9, 10, 11, 12), "ring": (13, 14, 15, 16),
            "pinky": (17, 18, 19, 20)}

STRAIGHT = (5.0, 5.0, 5.0)  # bend in degrees at MCP, PIP, DIP
CURLED = (80.0, 100.0, 60.0)
HALF = (35.0, 35.0, 20.0)

_THUMBS = {  # CMC, MCP, IP, TIP
    "out": [(-0.020, 0.020, 0.0), (-0.045, 0.040, 0.0), (-0.070, 0.058, 0.0), (-0.095, 0.070, 0.0)],
    # Tip-to-middle-MCP ratio about 0.68: inside the ambiguous band (thumb_in..thumb_out).
    "mid": [(-0.020, 0.020, 0.0), (-0.042, 0.040, 0.005), (-0.058, 0.060, 0.005), (-0.070, 0.075, 0.0)],
    "folded": [(-0.020, 0.020, 0.0), (-0.035, 0.040, 0.015), (-0.020, 0.052, 0.025), (0.000, 0.055, 0.020)],
}


def _finger(mcp_xy, segments, bends_deg) -> list[np.ndarray]:
    pts = [np.array([mcp_xy[0], mcp_xy[1], 0.0])]
    total = 0.0
    for seg, bend in zip(segments, bends_deg):
        total += math.radians(bend)
        pts.append(pts[-1] + seg * np.array([0.0, math.cos(total), math.sin(total)]))
    return pts


def make_hand(extended=(), thumb: str = "folded", bends: dict | None = None) -> np.ndarray:
    """(21, 3) world landmarks. Fingers in `extended` are straight, the rest curled."""
    bends = bends or {}
    lm = np.zeros((21, 3))
    lm[1:5] = _THUMBS[thumb]
    for name, idx in _INDICES.items():
        b = bends.get(name, STRAIGHT if name in extended else CURLED)
        lm[list(idx)] = _finger(_MCP[name], _SEGMENTS[name], b)
    return lm


def make_pinch() -> np.ndarray:
    lm = make_hand(bends={"index": HALF}, thumb="out")
    lm[4] = lm[8] + (0.004, 0.0, 0.0)
    return lm


def to_image(world: np.ndarray) -> np.ndarray:
    """A plausible normalised image projection: x right, y down, in [0, 1]."""
    img = np.empty_like(world)
    img[:, 0] = 0.5 + world[:, 0] * 2.0
    img[:, 1] = 0.7 - world[:, 1] * 2.0
    img[:, 2] = world[:, 2]
    return img


def random_rotation(seed: int) -> np.ndarray:
    q, r = np.linalg.qr(np.random.default_rng(seed).normal(size=(3, 3)))
    q *= np.sign(np.diag(r))
    if np.linalg.det(q) < 0:
        q[:, 0] *= -1
    return q
