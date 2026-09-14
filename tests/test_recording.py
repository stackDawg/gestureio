import numpy as np
import pytest

from gestureio.coordinator.recording import (PoseSegment, RecordingWriter, pose_timeline,
                                             read_recording)
from gestureio.coordinator.types import TrackedFace, TrackedHand
from handgen import make_hand, to_image

SIZE = (640, 480)


def _hand(extended, thumb, label):
    world = make_hand(extended, thumb)
    return TrackedHand(to_image(world), world, label, 0.97)


def test_round_trip(tmp_path):
    hand = _hand(("index", "middle"), "folded", "Right")
    path = tmp_path / "rec.jsonl"
    w = RecordingWriter(path, SIZE, "right-count2")
    w.write(100.0, [hand], [TrackedFace((0.1, 0.2, 0.3, 0.4), 0.9)])
    w.write(100.5, [], None)
    w.close()

    header, frames = read_recording(path)
    assert header["label"] == "right-count2" and header["frame_size"] == list(SIZE)
    assert header["mirrored"] is True
    assert [f.t for f in frames] == [0.0, 0.5]
    got = frames[0].hands[0]
    assert got.handedness == "Right"
    assert np.allclose(got.image_lm, hand.image_lm, atol=1e-5)
    assert np.allclose(got.world_lm, hand.world_lm, atol=1e-5)
    assert frames[0].faces[0].box == pytest.approx((0.1, 0.2, 0.3, 0.4))
    assert frames[1].hands == [] and frames[1].faces is None


def test_rejects_other_files(tmp_path):
    path = tmp_path / "x.jsonl"
    path.write_text('{"type": "something"}\n')
    with pytest.raises(ValueError):
        read_recording(path)


def test_pose_timeline_collapses_runs(tmp_path):
    right3 = _hand(("index", "middle", "ring"), "folded", "Right")
    palm = _hand(("index", "middle", "ring", "pinky"), "out", "Right")
    fist = _hand((), "folded", "Left")
    path = tmp_path / "rec.jsonl"
    w = RecordingWriter(path, SIZE)
    for i in range(15):
        w.write(i / 30, [right3 if i < 10 else palm, fist])
    w.close()

    _, frames = read_recording(path)
    segs = pose_timeline(frames, SIZE)
    assert segs == [
        PoseSegment("Left", "fist", 0.0, pytest.approx(14 / 30, abs=1e-4)),
        PoseSegment("Right", "count3", 0.0, pytest.approx(9 / 30, abs=1e-4)),
        PoseSegment("Right", "palm", pytest.approx(10 / 30, abs=1e-4), pytest.approx(14 / 30, abs=1e-4)),
    ]
