"""Which apps are using the webcam (or microphone) right now, from Windows' privacy records.

Windows logs every device session under the CapabilityAccessManager consent
store. An app whose LastUsedTimeStop is 0 has the device open. Store apps are
listed by package family name; desktop apps sit under "NonPackaged", named by
their exe path with "#" in place of "\\".

Windows only writes the stop time when a session ends cleanly, so an app that
crashed or updated mid-session stays "in use" forever. The laptop showed this
with an old Discord version folder (app-1.0.9255) listed permanently. So an
entry only counts if the app has a process running right now.
"""

from __future__ import annotations

import sys
import winreg
from dataclasses import dataclass

import psutil

CONSENT_STORE = r"SOFTWARE\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"


def store_roots(capability: str) -> tuple:
    path = rf"{CONSENT_STORE}\{capability}"
    return ((winreg.HKEY_CURRENT_USER, path), (winreg.HKEY_LOCAL_MACHINE, path))


@dataclass(frozen=True)
class DeviceUser:
    app: str  # package family name, or the exe path for desktop apps
    packaged: bool


def own_executables() -> set[str]:
    """This interpreter's paths; a venv python.exe hands off to the base interpreter."""
    paths = {sys.executable, getattr(sys, "_base_executable", sys.executable)}
    return {p.lower() for p in paths if p}


def running_executables() -> set[str]:
    exes = set()
    for proc in psutil.process_iter(["exe"]):
        exe = proc.info.get("exe")
        if exe:
            exes.add(exe.lower())
    return exes


def _packaged_running(family: str, running: set[str]) -> bool:
    # Family "Name_publisher" lives under WindowsApps\Name_version_arch__publisher\.
    name, _, publisher = family.lower().rpartition("_")
    return any(f"\\windowsapps\\{name}_" in exe and f"__{publisher}\\" in exe for exe in running)


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


def _open_sessions(roots) -> list[DeviceUser]:
    users: list[DeviceUser] = []
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
                                if _in_use(app):
                                    users.append(DeviceUser(exe_name.replace("#", "\\"), False))
                else:
                    with winreg.OpenKey(root, name) as app:
                        if _in_use(app):
                            users.append(DeviceUser(name, True))
    return users


def device_users(capability: str = "webcam", roots=None, exclude: set[str] | None = None,
                 running: set[str] | None = None) -> list[DeviceUser]:
    """Apps that have the device open and are actually running.

    Excludes this process's own interpreter by default.
    """
    candidates = _open_sessions(store_roots(capability) if roots is None else roots)
    if not candidates:
        return []
    exclude = own_executables() if exclude is None else {p.lower() for p in exclude}
    running = running_executables() if running is None else {p.lower() for p in running}
    live = []
    for user in candidates:
        if user.packaged:
            if _packaged_running(user.app, running):
                live.append(user)
        elif user.app.lower() in running and user.app.lower() not in exclude:
            live.append(user)
    return live


def webcam_users(**kwargs) -> list[DeviceUser]:
    return device_users("webcam", **kwargs)


def microphone_users(**kwargs) -> list[DeviceUser]:
    return device_users("microphone", **kwargs)
