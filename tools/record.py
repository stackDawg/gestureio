"""Record a labelled landmark stream for tuning and replay tests.

  uv run python tools/record.py right-count3                 10 s after a 3 s countdown
  uv run python tools/record.py pass-through --seconds 15

Writes recordings/<label>-<timestamp>.jsonl. Only landmarks are saved, never video.
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
import time
from datetime import datetime

import cv2

import _cli
from gestureio.common.paths import RECORDINGS_DIR
from gestureio.coordinator.capture import CameraError
from gestureio.coordinator.preview import AMBER, RED, draw_banner, draw_hand
from gestureio.coordinator.recording import RecordingWriter

WINDOW = "gestureio record"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("label", help="what the recording shows, e.g. right-count3")
    parser.add_argument("--seconds", type=float, default=10.0)
    parser.add_argument("--countdown", type=float, default=3.0)
    _cli.add_camera_args(parser)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        parser.error("label may only contain letters, digits, - and _")

    try:
        # Full rate throughout: a recording should never contain idle-mode gaps.
        pipeline = _cli.open_pipeline(args, active_fps=args.fps, idle_fps=args.fps)
    except (CameraError, *_cli.SETUP_ERRORS) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    path = RECORDINGS_DIR / f"{args.label}-{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    writer = None
    labels: collections.Counter[str] = collections.Counter()
    frames_with_hands = 0
    start = time.monotonic()
    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    try:
        while True:
            r = pipeline.next(timeout=1.0)
            if r is None:
                print("error: camera stopped delivering frames", file=sys.stderr)
                return 1
            elapsed = time.monotonic() - start
            canvas = r.image
            for hand, feat in zip(r.hands, r.features):
                draw_hand(canvas, hand.image_lm, feat)
            if elapsed < args.countdown:
                draw_banner(canvas, f"{args.label}: starting in {args.countdown - elapsed:.0f}", AMBER)
            else:
                if writer is None:
                    size = (canvas.shape[1], canvas.shape[0])
                    writer = RecordingWriter(path, size, args.label, camera=pipeline.capture.settings)
                writer.write(r.t_capture, r.hands, r.faces)
                frames_with_hands += bool(r.hands)
                labels.update(h.handedness for h in r.hands)
                left = args.countdown + args.seconds - elapsed
                if left <= 0:
                    break
                draw_banner(canvas, f"REC {args.label}  {left:.1f} s", RED)
            cv2.imshow(WINDOW, canvas)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                print("stopped early")
                break
    except KeyboardInterrupt:
        print("stopped early")
    finally:
        pipeline.close()
        cv2.destroyAllWindows()
        if writer is not None:
            writer.close()

    if writer is None or writer.frames == 0:
        print("nothing recorded")
        return 1
    print(f"saved {writer.frames} frames to {path}")
    print(f"frames with a hand: {frames_with_hands / writer.frames:.0%}; "
          f"labels seen: {dict(labels) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
