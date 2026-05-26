from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bizspot.pipeline import collect_building_api, collect_real_trade_api, load_config, setup_logging

setup_logging()
config = load_config()
collect_real_trade_api(config)
collect_building_api(config)

