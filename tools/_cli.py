"""Command-line options and setup shared by the camera tools."""

from __future__ import annotations

import argparse

from gestureio.coordinator.capture import BACKENDS, Capture
from gestureio.coordinator.pipeline import Pipeline


def add_camera_args(parser: argparse.ArgumentParser) -> None:
    g = parser.add_argument_group("camera")
    g.add_argument("--camera", type=int, default=0, help="camera index (default 0)")
    g.add_argument("--backend", choices=sorted(BACKENDS), default="msmf",
                   help="OpenCV capture backend (default msmf)")
    g.add_argument("--width", type=int, default=640)
    g.add_argument("--height", type=int, default=480)
    g.add_argument("--fps", type=int, default=30, help="frame rate to request from the camera")
    g.add_argument("--mjpg", action="store_true", help="request MJPG from the camera")
    g.add_argument("--process-width", type=int, default=640,
                   help="downscale wider frames to this before inference (0 = never)")
    g.add_argument("--invert-handedness", action="store_true",
                   help="swap Left/Right labels (only if the first-run check shows them inverted)")
    g.add_argument("--no-face", action="store_true", help="skip face detection")


def open_pipeline(args: argparse.Namespace, active_fps: float = 30.0,
                  idle_fps: float = 8.0) -> Pipeline:
    # Imported here so --help works even before the models are downloaded.
    from gestureio.coordinator.tracker import FaceTracker, HandTracker

    hands = HandTracker(invert_handedness=args.invert_handedness)
    faces = None if args.no_face else FaceTracker()
    capture = Capture(args.camera, args.width, args.height, args.fps, args.backend, args.mjpg)
    capture.start()
    return Pipeline(capture, hands, faces, active_fps=active_fps, idle_fps=idle_fps,
                    max_width=args.process_width or None)
