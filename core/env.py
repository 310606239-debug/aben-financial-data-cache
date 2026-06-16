from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from core.settings import REPO_ROOT


def load_dotenv(path: Optional[Path] = None) -> None:
    env_path = path or REPO_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
