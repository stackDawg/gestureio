"""Landmark recordings (JSON Lines) for tuning, replay and regression tests.

Only landmarks are stored, never images. The first line is a header; each later
line is one processed frame, with time in seconds since the first frame.
"""

from __future__ import annotations

import json
import platform
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from gestureio.coordinator.features import PoseThresholds, hand_features
from gestureio.coordinator.types import TrackedFace, TrackedHand

FORMAT_VERSION = 1


def _pts(a: np.ndarray) -> list:
    return np.round(a, 5).tolist()


class RecordingWriter:
    def __init__(self, path: Path, frame_size: tuple[int, int], label: str = "", **extra):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.frames = 0
        self._t0: float | None = None
        self._file = path.open("w", encoding="utf-8")
        header = {"type": "header", "version": FORMAT_VERSION, "label": label,
                  "frame_size": list(frame_size), "mirrored": True, "host": platform.node(),
                  "created": datetime.now().isoformat(timespec="seconds"), **extra}
        self._file.write(json.dumps(header) + "\n")

    def write(self, t: float, hands: list[TrackedHand], faces: list[TrackedFace] | None = None):
        if self._t0 is None:
            self._t0 = t
        line = {"t": round(t - self._t0, 4),
                "hands": [{"h": h.handedness, "s": round(h.score, 3), "img": _pts(h.image_lm),
                           "world": None if h.world_lm is None else _pts(h.world_lm)}
                          for h in hands]}
        if faces is not None:
            line["faces"] = [{"box": [round(v, 4) for v in f.box], "s": round(f.score, 3)}
                             for f in faces]
        self._file.write(json.dumps(line, separators=(",", ":")) + "\n")
        self.frames += 1

    def close(self) -> None:
        self._file.close()


@dataclass(frozen=True)
class RecordedFrame:
    t: float
    hands: list[TrackedHand]
    faces: list[TrackedFace] | None


def read_recording(path: Path) -> tuple[dict, list[RecordedFrame]]:
    with path.open(encoding="utf-8") as f:
        header = json.loads(f.readline())
        if header.get("type") != "header" or header.get("version") != FORMAT_VERSION:
            raise ValueError(f"{path} is not a version {FORMAT_VERSION} gestureio recording")
        frames = []
        for line in f:
            if not line.strip():
                continue
            d = json.loads(line)
            hands = [TrackedHand(np.array(h["img"]), None if h["world"] is None else np.array(h["world"]),
                                 h["h"], h["s"]) for h in d["hands"]]
            faces = None
            if "faces" in d:
                faces = [TrackedFace(tuple(x["box"]), x["s"]) for x in d["faces"]]
            frames.append(RecordedFrame(d["t"], hands, faces))
    return header, frames


@dataclass(frozen=True)
class PoseSegment:
    handedness: str
    pose: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def pose_timeline(frames: list[RecordedFrame], frame_size: tuple[int, int],
                  th: PoseThresholds = PoseThresholds()) -> list[PoseSegment]:
    """Collapse per-frame poses into runs per hand, for reading a recording at a glance."""
    open_runs: dict[str, tuple[str, float, float]] = {}  # hand -> (pose, start, last seen)
    segments: list[PoseSegment] = []
    for frame in frames:
        seen = {}
        for h in frame.hands:
            seen[h.handedness] = hand_features(h.image_lm, h.world_lm, h.handedness, h.score,
                                               frame_size, th).pose
        for hand, (pose, start, last) in list(open_runs.items()):
            if seen.get(hand) != pose:
                segments.append(PoseSegment(hand, pose, start, last))
                del open_runs[hand]
        for hand, pose in seen.items():
            start = open_runs[hand][1] if hand in open_runs else frame.t
            open_runs[hand] = (pose, start, frame.t)
    segments += [PoseSegment(hand, pose, start, last)
                 for hand, (pose, start, last) in open_runs.items()]
    return sorted(segments, key=lambda s: (s.start, s.handedness))
