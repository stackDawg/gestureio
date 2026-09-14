import numpy as np
import pytest

from gestureio.coordinator.features import EXT, FOLD, MID, hand_features
from handgen import HALF, make_hand, make_pinch, random_rotation, to_image

FRAME = (640, 480)


def features(world):
    return hand_features(to_image(world), world, "Right", 0.99, FRAME)


@pytest.mark.parametrize("extended, thumb, pose", [
    (("index", "middle", "ring", "pinky"), "out", "palm"),
    ((), "folded", "fist"),
    (("index",), "folded", "count1"),
    (("index", "middle"), "folded", "count2"),
    (("index", "middle", "ring"), "folded", "count3"),
    (("index", "middle", "ring", "pinky"), "folded", "count4"),
    (("index",), "out", "L"),
])
def test_poses(extended, thumb, pose):
    assert features(make_hand(extended, thumb)).pose == pose


def test_pinch_wins_over_other_poses():
    f = features(make_pinch())
    assert f.pose == "pinch"
    assert f.pinch_ratio < 0.1


def test_fist_with_thumb_on_index_is_not_a_pinch():
    world = make_hand((), "folded")
    world[4] = world[8] + (0.004, 0.0, 0.0)  # thumb tip resting on the curled index tip
    f = features(world)
    assert f.pinch_ratio < 0.30
    assert f.pose == "fist"


def test_straight_and_curled_fingers_are_far_from_thresholds():
    f = features(make_hand(("index",), "folded"))
    assert f.straightness["index"] > 0.95
    assert f.straightness["middle"] < 0.45
    assert f.fingers["index"] == EXT and f.fingers["middle"] == FOLD


def test_ambiguous_finger_refuses_to_count():
    f = features(make_hand(("index", "middle"), "folded", bends={"middle": HALF}))
    assert f.fingers["middle"] == MID
    assert f.pose == "other"


def test_ambiguous_thumb_is_neither_palm_nor_count4():
    # The G2-4 vs G1 safety margin: a half-out thumb must not launch or engage.
    f = features(make_hand(("index", "middle", "ring", "pinky"), "mid"))
    assert f.thumb == MID
    assert f.pose == "other"


@pytest.mark.parametrize("seed", range(5))
def test_pose_features_ignore_rotation_and_scale(seed):
    world = make_hand(("index", "middle"), "folded")
    moved = (world @ random_rotation(seed).T) * 0.7 + 0.3
    a, b = features(world), features(moved)
    assert b.pose == a.pose == "count2"
    assert b.thumb_ratio == pytest.approx(a.thumb_ratio)
    for name in a.straightness:
        assert b.straightness[name] == pytest.approx(a.straightness[name])


def test_image_landmarks_alone_are_a_usable_fallback():
    world = make_hand(("index", "middle", "ring", "pinky"), "out")
    f = hand_features(to_image(world), None, "Right", 0.9, FRAME)
    assert f.pose == "palm"


def test_knuckle_angle_uses_pixel_aspect():
    img = np.full((21, 3), 0.5)
    img[5, :2] = (0.5, 0.5)
    img[17, :2] = (0.6, 0.6)  # 64 px right, 48 px down on a 640x480 frame
    f = hand_features(img, None, "Left", 0.9, FRAME)
    assert f.knuckle_deg == pytest.approx(np.degrees(np.arctan2(48, 64)))


def test_bbox_area_and_center_are_normalised():
    f = features(make_hand(("index", "middle", "ring", "pinky"), "out"))
    assert 0.0 < f.bbox_area < 1.0
    assert 0.0 < f.center[0] < 1.0 and 0.0 < f.center[1] < 1.0
