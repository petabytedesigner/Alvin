from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


CONFIG_FILES = [
    "global.json",
    "features.json",
    "risk.json",
    "scoring.json",
    "instruments.json",
]


def load_all_configs(config_dir: str = "config") -> Dict[str, Any]:
    base = Path(config_dir)
    if not base.exists():
        raise FileNotFoundError(f"Missing config directory: {config_dir}")

    loaded: Dict[str, Any] = {}
    for name in CONFIG_FILES:
        path = base / name
        if not path.exists():
            raise FileNotFoundError(f"Missing config file: {path}")
        loaded[path.stem] = json.loads(path.read_text(encoding="utf-8"))

    return loaded
