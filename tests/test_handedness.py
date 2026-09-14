"""The left/right mapping: the classic silent-inversion bug, pinned down."""

import mediapipe

from gestureio.coordinator.tracker import VERIFIED_MEDIAPIPE, user_hand


def test_mirrored_frame_label_is_the_opposite_hand():
    # Measured on the laptop bench: raising the right hand, MediaPipe said "Left".
    assert user_hand("Left") == "Right"
    assert user_hand("Right") == "Left"


def test_invert_flag_undoes_the_correction():
    assert user_hand("Left", invert=True) == "Left"
    assert user_hand("Right", invert=True) == "Right"


def test_unknown_labels_pass_through():
    assert user_hand("") == ""


def test_convention_was_verified_on_the_installed_mediapipe():
    # Fails after a MediaPipe upgrade on purpose: redo the bench right/left check,
    # then update VERIFIED_MEDIAPIPE in tracker.py.
    assert mediapipe.__version__ == VERIFIED_MEDIAPIPE
