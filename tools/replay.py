"""Replay a landmark recording as a skeleton animation, or print it as a pose timeline.

  uv run python tools/replay.py recordings/right-count3-20260914-201500.jsonl
  uv run python tools/replay.py recordings/right-count3-20260914-201500.jsonl --text

Window keys: space pause, q quit.
"""

from __future__ import annotations

import argparse
import collections
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from gestureio.coordinator.features import hand_features
from gestureio.coordinator.preview import draw_banner, draw_faces, draw_hand
from gestureio.coordinator.recording import pose_timeline, read_recording

WINDOW = "gestureio replay"


def print_text(path: Path, header: dict, frames, min_duration: float) -> None:
    size = tuple(header["frame_size"])
    duration = frames[-1].t if frames else 0.0
    with_hands = sum(bool(f.hands) for f in frames)
    labels = collections.Counter(h.handedness for f in frames for h in f.hands)
    print(f"{path.name}: label={header.get('label')!r} host={header.get('host')} "
          f"{len(frames)} frames over {duration:.1f} s ({len(frames) / max(duration, 1e-9):.1f} fps)")
    print(f"frames with a hand: {with_hands / max(len(frames), 1):.0%}; labels: {dict(labels)}")
    segments = pose_timeline(frames, size)
    shown = [s for s in segments if s.duration >= min_duration]
    print(f"pose runs of at least {min_duration:.2f} s ({len(segments) - len(shown)} shorter blips hidden):")
    for s in shown:
        print(f"  {s.start:6.2f} - {s.end:6.2f} s  ({s.duration:4.2f} s)  {s.handedness:5}  {s.pose}")


def play(header: dict, frames, speed: float) -> None:
    w, h = header["frame_size"]
    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    start = time.monotonic()
    paused_at = None
    i = 0
    while i < len(frames):
        if paused_at is None and frames[i].t / speed > time.monotonic() - start:
            key = cv2.waitKey(1) & 0xFF
        else:
            f = frames[i]
            canvas = np.full((h, w, 3), 40, np.uint8)
            for hand in f.hands:
                feat = hand_features(hand.image_lm, hand.world_lm, hand.handedness, hand.score, (w, h))
                draw_hand(canvas, hand.image_lm, feat)
            if f.faces:
                draw_faces(canvas, f.faces)
            draw_banner(canvas, f"{f.t:6.2f} s  {'PAUSED' if paused_at else ''}", scale=0.6)
            cv2.imshow(WINDOW, canvas)
            if paused_at is None:
                i += 1
            key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27) or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
            break
        if key == ord(" "):
            if paused_at is None:
                paused_at = time.monotonic()
            else:
                start += time.monotonic() - paused_at
                paused_at = None
    cv2.destroyAllWindows()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("path", type=Path)
    parser.add_argument("--text", action="store_true", help="print a pose timeline instead")
    parser.add_argument("--min-duration", type=float, default=0.1,
                        help="hide pose runs shorter than this in --text (seconds)")
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()
    header, frames = read_recording(args.path)
    if args.text:
        print_text(args.path, header, frames, args.min_duration)
    else:
        play(header, frames, args.speed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
