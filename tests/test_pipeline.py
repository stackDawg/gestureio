"""Pipeline behaviour with a fake camera and tracker: mirroring, and idle throttling."""

import numpy as np

from gestureio.coordinator.capture import Frame
from gestureio.coordinator.pipeline import Pipeline
from gestureio.coordinator.types import TrackedHand
from handgen import make_hand, to_image


class FakeCapture:
    def __init__(self, images, fps=30.0):
        self.frames = [Frame(img, i / fps, i + 1) for i, img in enumerate(images)]
        self.fps, self.width, self.height = fps, 640, 480
        self.stopped = False

    def latest(self, after_seq=0, timeout=1.0):
        # Hands out every frame in order, like a camera the pipeline keeps up with.
        return self.frames[after_seq] if after_seq < len(self.frames) else None

    def stop(self):
        self.stopped = True


class FakeTracker:
    def __init__(self, with_hand: bool):
        self.seen = []
        world = make_hand(("index",), "folded")
        self.hand = TrackedHand(to_image(world), world, "Right", 0.95)
        self.with_hand = with_hand

    def detect(self, rgb, t):
        self.seen.append(rgb.copy())
        return [self.hand] if self.with_hand else []

    def close(self):
        pass


def _blank(n):
    return [np.zeros((480, 640, 3), np.uint8) for _ in range(n)]


def test_frames_are_mirrored_exactly_once_and_converted_to_rgb():
    img = np.zeros((480, 640, 3), np.uint8)
    img[:, :50] = (255, 0, 0)  # BGR blue on the camera's left edge
    tracker = FakeTracker(with_hand=False)
    result = Pipeline(FakeCapture([img]), tracker).next()

    rgb = tracker.seen[0]
    assert (rgb[:, -50:] == (0, 0, 255)).all(), "model input should be mirrored RGB"
    assert (rgb[:, :-50] == 0).all()
    assert (result.image[:, -50:] == (255, 0, 0)).all(), "preview image is mirrored BGR"


def test_oversized_frames_are_downscaled_before_mirroring():
    img = np.zeros((720, 1280, 3), np.uint8)
    img[:, :100] = (255, 0, 0)
    tracker = FakeTracker(with_hand=False)
    result = Pipeline(FakeCapture([img]), tracker, max_width=640).next()

    rgb = tracker.seen[0]
    assert rgb.shape == (360, 640, 3)
    assert (rgb[:, -49:] == (0, 0, 255)).all() and (rgb[:, :-51] == 0).all()
    assert result.image.shape == (360, 640, 3)


def test_idle_pipeline_throttles_to_idle_rate():
    pipe = Pipeline(FakeCapture(_blank(60)), FakeTracker(with_hand=False), active_fps=30, idle_fps=8)
    results = [r for r in iter(pipe.next, None)]
    assert 13 <= len(results) <= 17  # about 8 fps over 2 s
    assert pipe.idle


def test_active_pipeline_processes_every_frame_and_computes_features():
    pipe = Pipeline(FakeCapture(_blank(60)), FakeTracker(with_hand=True), active_fps=30, idle_fps=8)
    results = [r for r in iter(pipe.next, None)]
    assert len(results) == 60
    assert not pipe.idle
    assert results[-1].features[0].pose == "count1"
    assert results[-1].features[0].handedness == "Right"


def test_close_stops_capture():
    cap = FakeCapture(_blank(1))
    Pipeline(cap, FakeTracker(with_hand=False)).close()
    assert cap.stopped
