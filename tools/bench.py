"""Phase 0 bench: live hand tracking with handedness, pose readouts and resource use.

  uv run python tools/bench.py                  preview window
  uv run python tools/bench.py --measure 600    headless for 10 minutes, then a report
  uv run python tools/bench.py --backend dshow  try the DirectShow camera backend

Preview keys: q quit, r start/stop a landmark recording, h hide/show the HUD.
Every run writes a JSON report to bench_results/.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import datetime

import cv2
import numpy as np
import psutil

import _cli
from gestureio.common.paths import BENCH_RESULTS_DIR, RECORDINGS_DIR
from gestureio.coordinator.camera_guard import webcam_users
from gestureio.coordinator.capture import CameraError
from gestureio.coordinator.preview import (AMBER, GREEN, RED, WHITE, draw_banner, draw_faces,
                                           draw_hand, draw_hud)
from gestureio.coordinator.recording import RecordingWriter

CPU_BUDGET_PCT = {"idle": 5.0, "active": 20.0}  # share of the whole CPU, from the plan
WINDOW = "gestureio bench"


def _pct(values, q):
    return round(float(np.percentile(values, q)), 1) if values else None


class Stats:
    """Per-second resource samples plus per-frame timings, split by idle/active mode."""

    def __init__(self):
        self.proc = psutil.Process()
        self.proc.cpu_percent(None)  # the first call only starts the measurement
        self.ncpu = psutil.cpu_count(logical=True) or 1
        self.seconds: list[dict] = []
        self.frames: list[tuple[str, float, float | None, float]] = []
        self.start = self._window = time.monotonic()
        self._count = 0

    def frame(self, r, mode: str) -> None:
        self._count += 1
        self.frames.append((mode, r.hand_ms, r.face_ms, (r.t_done - r.t_capture) * 1000.0))

    def tick(self, pipeline) -> dict | None:
        now = time.monotonic()
        if now - self._window < 1.0:
            return None
        sample = {
            "t": round(now - self.start, 1),
            "mode": "idle" if pipeline.idle else "active",
            "cpu_pct": round(self.proc.cpu_percent(None) / self.ncpu, 2),
            "infer_fps": round(self._count / (now - self._window), 1),
            "cam_fps": round(pipeline.capture.fps, 1),
            "frame_age_ms": round(min(pipeline.capture.frame_age, 99.0) * 1000.0),
        }
        self.seconds.append(sample)
        self._window, self._count = now, 0
        return sample

    def summary(self) -> dict:
        out: dict = {}
        for mode, budget in CPU_BUDGET_PCT.items():
            secs = [s for s in self.seconds if s["mode"] == mode]
            if not secs:
                continue
            frames = [f for f in self.frames if f[0] == mode]
            cpu = [s["cpu_pct"] for s in secs]
            out[mode] = {
                "seconds": len(secs),
                "cpu_pct_median": _pct(cpu, 50),
                "cpu_pct_p95": _pct(cpu, 95),
                "cpu_budget_pct": budget,
                "within_budget": _pct(cpu, 50) <= budget,
                "infer_fps_mean": round(float(np.mean([s["infer_fps"] for s in secs])), 1),
                "cam_fps_mean": round(float(np.mean([s["cam_fps"] for s in secs])), 1),
                "hand_ms_p50": _pct([f[1] for f in frames], 50),
                "hand_ms_p95": _pct([f[1] for f in frames], 95),
                "face_ms_p50": _pct([f[2] for f in frames if f[2] is not None], 50),
                "read_to_features_ms_p50": _pct([f[3] for f in frames], 50),
                "read_to_features_ms_p95": _pct([f[3] for f in frames], 95),
            }
        out["stalled_seconds"] = sum(s["frame_age_ms"] > 1000 for s in self.seconds)
        return out


class CameraWatch:
    """Polls which other apps have the webcam open, logging every change."""

    def __init__(self):
        self.current: list[str] = []
        self.log: list[dict] = []
        self._next = 0.0

    def poll(self, t_rel: float) -> None:
        now = time.monotonic()
        if now < self._next:
            return
        self._next = now + 2.0
        apps = sorted(u.app for u in webcam_users())
        if apps != self.current or not self.log:
            self.log.append({"t": round(t_rel, 1), "apps": apps})
            self.current = apps


def hud_lines(pipeline, stats: Stats, watch: CameraWatch, r, writer) -> list[tuple[str, tuple]]:
    cam = pipeline.capture
    s = stats.seconds[-1] if stats.seconds else None
    mode = "idle" if pipeline.idle else "active"
    processed = f" -> {r.image.shape[1]}x{r.image.shape[0]}" if r is not None else ""
    lines = [(f"camera {cam.settings.get('width')}x{cam.settings.get('height')}{processed} "
              f"{cam.settings.get('backend')}  {cam.fps:.1f} fps", WHITE)]
    if s:
        budget = CPU_BUDGET_PCT[mode]
        lines.append((f"inference {s['infer_fps']:.1f} fps [{mode}]   "
                      f"cpu {s['cpu_pct']:.1f}% of total (budget {budget:.0f}%)",
                      GREEN if s["cpu_pct"] <= budget else AMBER))
    if r is not None:
        face = f"{r.face_ms:.0f} ms" if r.face_ms is not None else "-"
        lines.append((f"hand {r.hand_ms:.0f} ms  face {face}  "
                      f"read->features {(r.t_done - r.t_capture) * 1000:.0f} ms", WHITE))
    others = ", ".join(a.rsplit("\\", 1)[-1] for a in watch.current) or "none"
    lines.append((f"other apps using camera: {others}", AMBER if watch.current else WHITE))
    recent = [m for t, m in cam.events if time.monotonic() - t < 10.0]
    if recent:
        lines.append((recent[-1], AMBER))
    if writer is not None:
        lines.append((f"REC {writer.frames} frames -> {writer.path.name}", RED))
    return lines


def run_preview(pipeline, stats: Stats, watch: CameraWatch) -> None:
    cv2.namedWindow(WINDOW, cv2.WINDOW_AUTOSIZE)
    show_hud, writer, last_faces, canvas = True, None, [], None
    try:
        while True:
            r = pipeline.next(timeout=1.0)
            stats.tick(pipeline)
            watch.poll(time.monotonic() - stats.start)
            if r is None:
                canvas = (canvas * 0.4).astype(np.uint8) if canvas is not None else \
                    np.zeros((pipeline.capture.height, pipeline.capture.width, 3), np.uint8)
                draw_banner(canvas, "NO FRAMES - camera stalled or taken", RED)
            else:
                stats.frame(r, "idle" if pipeline.idle else "active")
                if r.faces is not None:
                    last_faces = r.faces
                if writer is not None:
                    writer.write(r.t_capture, r.hands, r.faces)
                canvas = r.image
                for hand, feat in zip(r.hands, r.features):
                    draw_hand(canvas, hand.image_lm, feat)
                draw_faces(canvas, last_faces)
            if show_hud:
                draw_hud(canvas, hud_lines(pipeline, stats, watch, r, writer))
            cv2.imshow(WINDOW, canvas)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27) or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == ord("h"):
                show_hud = not show_hud
            elif key == ord("r"):
                if writer is None:
                    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                    size = (canvas.shape[1], canvas.shape[0])
                    writer = RecordingWriter(RECORDINGS_DIR / f"bench-{stamp}.jsonl", size, "bench")
                else:
                    writer.close()
                    print(f"saved {writer.frames} frames to {writer.path}")
                    writer = None
    finally:
        if writer is not None:
            writer.close()
            print(f"saved {writer.frames} frames to {writer.path}")
        cv2.destroyAllWindows()


def run_headless(pipeline, stats: Stats, watch: CameraWatch, seconds: float) -> None:
    print(f"Measuring for {seconds:.0f} s. Keep hands out of view for a while (idle numbers),\n"
          "then gesture in front of the camera (active numbers). Ctrl+C stops early.")
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        r = pipeline.next(timeout=1.0)
        if r is not None:
            stats.frame(r, "idle" if pipeline.idle else "active")
        s = stats.tick(pipeline)
        watch.poll(time.monotonic() - stats.start)
        if s and len(stats.seconds) % 10 == 0:
            print(f"  {s['t']:6.0f}s  {s['mode']:6}  cpu {s['cpu_pct']:5.1f}%  "
                  f"inference {s['infer_fps']:4.1f} fps  camera {s['cam_fps']:4.1f} fps")


def save_report(args, pipeline, stats: Stats, watch: CameraWatch) -> tuple[dict, str]:
    import mediapipe as mp

    report = {
        "host": platform.node(),
        "created": datetime.now().isoformat(timespec="seconds"),
        "cpu": platform.processor(),
        "logical_cpus": stats.ncpu,
        "python": platform.python_version(),
        "mediapipe": mp.__version__,
        "opencv": cv2.__version__,
        "args": vars(args),
        "camera": pipeline.capture.settings,
        "preview_window": args.measure is None,
        "summary": stats.summary(),
        "camera_users": watch.log,
        "capture_events": [{"t": round(t - stats.start, 1), "msg": m}
                           for t, m in pipeline.capture.events],
        "seconds": stats.seconds,
    }
    BENCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = BENCH_RESULTS_DIR / f"bench-{platform.node()}-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report, str(path)


def print_summary(report: dict, path: str) -> None:
    summary = report["summary"]
    print(f"\nCamera: {report['camera']}")
    for mode in ("idle", "active"):
        m = summary.get(mode)
        if not m:
            print(f"{mode:>6}: no samples")
            continue
        verdict = "within budget" if m["within_budget"] else "OVER BUDGET"
        print(f"{mode:>6}: {m['seconds']} s, cpu median {m['cpu_pct_median']}% "
              f"(p95 {m['cpu_pct_p95']}%, budget {m['cpu_budget_pct']}%: {verdict}), "
              f"inference {m['infer_fps_mean']} fps, hand model p50 {m['hand_ms_p50']} ms "
              f"/ p95 {m['hand_ms_p95']} ms")
    print(f"stalled seconds: {summary['stalled_seconds']}")
    print(f"other apps seen using the camera: {report['camera_users']}")
    print(f"report: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    _cli.add_camera_args(parser)
    parser.add_argument("--active-fps", type=float, default=30.0)
    parser.add_argument("--idle-fps", type=float, default=8.0)
    parser.add_argument("--measure", type=float, metavar="SECONDS",
                        help="run without a window for this long and report resource use")
    args = parser.parse_args()

    try:
        pipeline = _cli.open_pipeline(args, args.active_fps, args.idle_fps)
    except (CameraError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    stats, watch = Stats(), CameraWatch()
    try:
        if args.measure:
            run_headless(pipeline, stats, watch, args.measure)
        else:
            run_preview(pipeline, stats, watch)
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.close()
    print_summary(*save_report(args, pipeline, stats, watch))
    return 0


if __name__ == "__main__":
    sys.exit(main())
