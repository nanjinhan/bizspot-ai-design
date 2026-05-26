from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bizspot.pipeline import export_web_data, setup_logging

setup_logging()
export_web_data()

