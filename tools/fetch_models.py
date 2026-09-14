"""Download the MediaPipe model files the coordinator needs into models/.

Run once per machine:  uv run python tools/fetch_models.py
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import urllib.request

from gestureio.common.paths import MODELS_DIR

_BASE = "https://storage.googleapis.com/mediapipe-models"
# name -> (url, sha256). The URLs are versioned, so the hashes should never change.
MODELS = {
    "hand_landmarker.task": (
        f"{_BASE}/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task",
        "fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1",
    ),
    "blaze_face_short_range.tflite": (
        f"{_BASE}/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite",
        "b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f",
    ),
}


def fetch(name: str, url: str, sha256: str) -> bool:
    dest = MODELS_DIR / name
    if not dest.exists():
        tmp = dest.with_name(dest.name + ".part")
        print(f"downloading {name} ...")
        with urllib.request.urlopen(url, timeout=60) as resp, tmp.open("wb") as out:
            shutil.copyfileobj(resp, out)
        tmp.replace(dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    if digest != sha256:
        print(f"{name}: HASH MISMATCH (got {digest}); delete {dest} and retry", file=sys.stderr)
        return False
    print(f"{name}: ok ({dest.stat().st_size:,} bytes)")
    return True


def main() -> int:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    results = [fetch(name, url, sha) for name, (url, sha) in MODELS.items()]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
