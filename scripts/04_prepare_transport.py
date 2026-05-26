from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bizspot.pipeline import load_manifest, preprocess_transport, setup_logging

setup_logging()
preprocess_transport(load_manifest())

