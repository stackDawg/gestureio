import sys
from pathlib import Path

# Lets tests import the shared helpers in this folder (e.g. handgen).
sys.path.insert(0, str(Path(__file__).parent))
