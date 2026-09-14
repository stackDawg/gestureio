import uuid
import winreg

import pytest

from gestureio.coordinator.camera_guard import CameraUser, webcam_users


def _set_session(parent, name, start, stop):
    with winreg.CreateKey(parent, name) as key:
        winreg.SetValueEx(key, "LastUsedTimeStart", 0, winreg.REG_QWORD, start)
        winreg.SetValueEx(key, "LastUsedTimeStop", 0, winreg.REG_QWORD, stop)


def _delete_tree(hive, path):
    with winreg.OpenKey(hive, path) as key:
        children = []
        while True:
            try:
                children.append(winreg.EnumKey(key, len(children)))
            except OSError:
                break
    for child in children:
        _delete_tree(hive, rf"{path}\{child}")
    winreg.DeleteKey(hive, path)


@pytest.fixture
def fake_store():
    path = rf"Software\gestureio-test-{uuid.uuid4().hex}\webcam"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as root:
        _set_session(root, "Some.App_abc123", 5, 0)
        _set_session(root, "Old.App_def456", 5, 9)
        with winreg.CreateKey(root, "NonPackaged") as nonpackaged:
            _set_session(nonpackaged, r"C:#Tools#Discord.exe", 5, 0)
            _set_session(nonpackaged, r"C:#Python#python.exe", 5, 0)
            _set_session(nonpackaged, r"C:#Tools#closed.exe", 5, 7)
    yield (winreg.HKEY_CURRENT_USER, path)
    _delete_tree(winreg.HKEY_CURRENT_USER, path.rsplit("\\", 1)[0])


def test_reports_open_sessions_and_skips_excluded(fake_store):
    users = webcam_users(roots=[fake_store], exclude={r"c:\python\python.exe"})
    assert sorted(users, key=lambda u: u.app) == [
        CameraUser(r"C:\Tools\Discord.exe", packaged=False),
        CameraUser("Some.App_abc123", packaged=True),
    ]


def test_missing_store_is_empty():
    assert webcam_users(roots=[(winreg.HKEY_CURRENT_USER, r"Software\no-such-gestureio-key")]) == []
