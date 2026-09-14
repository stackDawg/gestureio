"""One Euro filter (Casiez et al., 2012) for smoothing landmark signals.

It smooths heavily while the hand is still, killing jitter, and lightly while it
moves fast, keeping lag low. Works on floats and on numpy arrays element-wise.
"""

from __future__ import annotations

import math

import numpy as np


def _alpha(cutoff, dt: float):
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuroFilter:
    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.0, d_cutoff: float = 1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    def reset(self) -> None:
        self._x = None
        self._dx = None
        self._t: float | None = None

    def __call__(self, x, t: float):
        x = np.asarray(x, dtype=float)
        if self._x is None:
            self._x, self._dx, self._t = x, np.zeros_like(x), t
            return x.copy() if x.ndim else float(x)
        dt = t - self._t
        if dt <= 0.0:
            return self._x.copy() if self._x.ndim else float(self._x)
        dx = (x - self._x) / dt
        a_d = _alpha(self.d_cutoff, dt)
        edx = self._dx + a_d * (dx - self._dx)
        cutoff = self.min_cutoff + self.beta * np.abs(edx)
        a = _alpha(cutoff, dt)
        x_hat = self._x + a * (x - self._x)
        self._x, self._dx, self._t = x_hat, edx, t
        return x_hat.copy() if x_hat.ndim else float(x_hat)
