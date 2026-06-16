from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.settings import DCF_CACHE_DIR, MANIFEST_PATH, SCHEMA_VERSION, SOURCE_NAME


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write("\n")
        temporary_path.replace(path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def write_stock_cache(payload: dict[str, Any]) -> Path:
    path = DCF_CACHE_DIR / f"{payload['symbol']}.json"
    write_json_atomic(path, payload)
    return path


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {
            "schema_version": SCHEMA_VERSION,
            "source": SOURCE_NAME,
            "generated_at": None,
            "stocks": {},
        }
    with MANIFEST_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def update_manifest(
    successes: list[dict[str, Any]],
    failures: dict[str, str],
) -> None:
    manifest = load_manifest()
    stocks = manifest.setdefault("stocks", {})

    for payload in successes:
        symbol = payload["symbol"]
        stocks[symbol] = {
            "status": "ok",
            "fetched_at": payload["fetched_at"],
            "as_of": payload["market_data"]["as_of"],
            "market": payload["market"],
            "indexes": payload["indexes"],
            "forward_models": sorted(
                payload["calculator_contract"]["forward_models"]
            ),
            "path": f"cache/dcf/{symbol}.json",
        }

    for symbol, error in failures.items():
        previous = stocks.get(symbol, {})
        stocks[symbol] = {
            **previous,
            "status": "error",
            "last_attempt_at": datetime.now(timezone.utc).isoformat(),
            "error": error,
        }

    manifest.update(
        {
            "schema_version": SCHEMA_VERSION,
            "source": SOURCE_NAME,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stocks": dict(sorted(stocks.items())),
        }
    )
    write_json_atomic(MANIFEST_PATH, manifest)
