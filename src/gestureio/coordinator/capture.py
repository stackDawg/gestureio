"""Webcam capture on a background thread that keeps only the newest frame.

The inference loop always takes the most recent frame and never works through a
backlog, so a slow inference costs one frame of latency instead of a growing queue.
"""

from __future__ import annotations

import os

# Without this, OpenCV's Media Foundation backend can take 10+ s to open a camera.
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

import collections
import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

BACKENDS = {"msmf": cv2.CAP_MSMF, "dshow": cv2.CAP_DSHOW}
_REOPEN_AFTER_FAILURES = 15
_REOPEN_INTERVAL_S = 2.0


class CameraError(RuntimeError):
    pass


@dataclass(frozen=True)
class Frame:
    image: np.ndarray  # BGR, exactly as the camera delivered it (not mirrored)
    t: float  # time.monotonic() when the read returned
    seq: int


class Capture:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480, fps: int = 30,
                 backend: str = "msmf", mjpg: bool = False):
        if backend not in BACKENDS:
            raise ValueError(f"backend must be one of {sorted(BACKENDS)}")
        self.index, self.width, self.height, self.req_fps = index, width, height, fps
        self.backend, self.mjpg = backend, mjpg
        self.fps = 0.0  # measured delivery rate, smoothed
        self.settings: dict = {}  # what the driver actually granted
        self.events: collections.deque[tuple[float, str]] = collections.deque(maxlen=20)
        self._cond = threading.Condition()
        self._frame: Frame | None = None
        self._seq = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._cap: cv2.VideoCapture | None = None

    def start(self) -> None:
        self._cap = self._open()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                return  # stuck inside a driver read; releasing now could crash
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def latest(self, after_seq: int = 0, timeout: float = 1.0) -> Frame | None:
        """The newest frame with seq > after_seq, waiting up to timeout for one."""
        with self._cond:
            self._cond.wait_for(lambda: self._frame is not None and self._frame.seq > after_seq,
                                timeout)
            frame = self._frame
        return frame if frame is not None and frame.seq > after_seq else None

    @property
    def frame_age(self) -> float:
        with self._cond:
            frame = self._frame
        return time.monotonic() - frame.t if frame is not None else float("inf")

    def _log(self, message: str) -> None:
        self.events.append((time.monotonic(), message))

    def _open(self) -> cv2.VideoCapture:
        cap = cv2.VideoCapture(self.index, BACKENDS[self.backend])
        if not cap.isOpened():
            cap.release()
            raise CameraError(f"could not open camera {self.index} with {self.backend}")
        if self.mjpg:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.req_fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.settings = {
            "backend": cap.getBackendName(),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": cap.get(cv2.CAP_PROP_FPS),
        }
        s = self.settings
        self._log(f"opened camera {self.index} via {s['backend']}: {s['width']}x{s['height']} @ {s['fps']:.0f}")
        return cap

    def _run(self) -> None:
        failures = 0
        last_t: float | None = None
        while not self._stop.is_set():
            if self._cap is None:
                try:
                    self._cap = self._open()
                    failures = 0
                except CameraError as exc:
                    self._log(str(exc))
                    self._stop.wait(_REOPEN_INTERVAL_S)
                    continue
            ok, image = self._cap.read()
            now = time.monotonic()
            if not ok or image is None:
                failures += 1
                if failures >= _REOPEN_AFTER_FAILURES:
                    self._log("camera stopped delivering frames; reopening")
                    self._cap.release()
                    self._cap = None
                    last_t = None
                else:
                    self._stop.wait(0.01)
                continue
            failures = 0
            if last_t is not None and now > last_t:
                inst = 1.0 / (now - last_t)
                self.fps = inst if self.fps == 0.0 else 0.9 * self.fps + 0.1 * inst
            last_t = now
            with self._cond:
                self._seq += 1
                self._frame = Frame(image, now, self._seq)
                self._cond.notify_all()
