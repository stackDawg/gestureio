"""Which apps are using the webcam right now, from Windows' privacy records.

Windows logs every camera session under the CapabilityAccessManager consent
store. An app whose LastUsedTimeStop is 0 currently has the camera open. Store
apps are listed by package family name; desktop apps sit under "NonPackaged",
named by their exe path with "#" in place of "\\".
"""

from __future__ import annotations

import sys
import winreg
from dataclasses import dataclass

WEBCAM_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam"
DEFAULT_ROOTS = ((winreg.HKEY_CURRENT_USER, WEBCAM_KEY), (winreg.HKEY_LOCAL_MACHINE, WEBCAM_KEY))


@dataclass(frozen=True)
class CameraUser:
    app: str  # package family name, or the exe path for desktop apps
    packaged: bool


def own_executables() -> set[str]:
    """This interpreter's paths; a venv python.exe hands off to the base interpreter."""
    paths = {sys.executable, getattr(sys, "_base_executable", sys.executable)}
    return {p.lower() for p in paths if p}


def _in_use(key) -> bool:
    try:
        start, _ = winreg.QueryValueEx(key, "LastUsedTimeStart")
        stop, _ = winreg.QueryValueEx(key, "LastUsedTimeStop")
    except OSError:
        return False
    return start != 0 and stop == 0


def _subkeys(key):
    i = 0
    while True:
        try:
            yield winreg.EnumKey(key, i)
        except OSError:
            return
        i += 1


def webcam_users(roots=DEFAULT_ROOTS, exclude: set[str] | None = None) -> list[CameraUser]:
    """Apps with the camera open, excluding this process's own interpreter by default."""
    exclude = own_executables() if exclude is None else {p.lower() for p in exclude}
    users: list[CameraUser] = []
    for hive, path in roots:
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        with root:
            for name in list(_subkeys(root)):
                if name == "NonPackaged":
                    with winreg.OpenKey(root, name) as nonpackaged:
                        for exe_name in list(_subkeys(nonpackaged)):
                            with winreg.OpenKey(nonpackaged, exe_name) as app:
                                exe = exe_name.replace("#", "\\")
                                if _in_use(app) and exe.lower() not in exclude:
                                    users.append(CameraUser(exe, packaged=False))
                else:
                    with winreg.OpenKey(root, name) as app:
                        if _in_use(app):
                            users.append(CameraUser(name, packaged=True))
    return users
