"""Filesystem locations shared by the coordinator, agent and tools."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODELS_DIR = Path(os.environ.get("GESTUREIO_MODELS", REPO_ROOT / "models"))
RECORDINGS_DIR = REPO_ROOT / "recordings"
BENCH_RESULTS_DIR = REPO_ROOT / "bench_results"
