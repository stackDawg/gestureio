import uuid
import winreg

import pytest

from gestureio.coordinator.camera_guard import DeviceUser, device_users, running_executables

RUNNING = {
    r"C:\Tools\Discord.exe",
    r"C:\Python\python.exe",
    r"C:\Program Files\WindowsApps\Some.App_1.2.3.0_x64__abc123\App.exe",
}


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
        _set_session(root, "NotRunning.App_zzz999", 5, 0)
        with winreg.CreateKey(root, "NonPackaged") as nonpackaged:
            _set_session(nonpackaged, r"C:#Tools#Discord.exe", 5, 0)
            _set_session(nonpackaged, r"C:#Python#python.exe", 5, 0)
            _set_session(nonpackaged, r"C:#Tools#closed.exe", 5, 7)
            # Left open by a crash or an update: no process runs from this path.
            _set_session(nonpackaged, r"C:#Tools#app-1.0.9255#Discord.exe", 5, 0)
    yield (winreg.HKEY_CURRENT_USER, path)
    _delete_tree(winreg.HKEY_CURRENT_USER, path.rsplit("\\", 1)[0])


def test_reports_live_sessions_only(fake_store):
    users = device_users(roots=[fake_store], exclude={r"c:\python\python.exe"}, running=RUNNING)
    assert sorted(users, key=lambda u: u.app) == [
        DeviceUser(r"C:\Tools\Discord.exe", packaged=False),
        DeviceUser("Some.App_abc123", packaged=True),
    ]


def test_stale_sessions_are_ignored(fake_store):
    users = device_users(roots=[fake_store], exclude=set(), running=set())
    assert users == []


def test_missing_store_is_empty():
    assert device_users(roots=[(winreg.HKEY_CURRENT_USER, r"Software\no-such-gestureio-key")]) == []


def test_running_executables_sees_processes():
    assert len(running_executables()) > 5
