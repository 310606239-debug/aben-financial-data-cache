from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.cache import write_json_atomic
from core.settings import DCF_CACHE_DIR, UNIVERSE_PATH


SYNC_FIELDS = ("name", "exchange", "currency", "market", "indexes")


def load_universe_metadata(path: Path = UNIVERSE_PATH) -> dict[str, dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)

    metadata: dict[str, dict[str, Any]] = {}
    for stock in payload.get("stocks", []):
        if not stock.get("enabled", True):
            continue
        symbol = str(stock.get("symbol", "")).strip().upper()
        if not symbol:
            continue
        metadata[symbol] = {
            "name": stock.get("name", symbol),
            "exchange": stock.get("exchange"),
            "currency": stock.get("currency"),
            "market": stock.get("market"),
            "indexes": sorted(stock.get("indexes", [])),
        }
    return metadata


def reconcile_cache_metadata(
    cache_dir: Path = DCF_CACHE_DIR,
    universe_path: Path = UNIVERSE_PATH,
) -> int:
    universe = load_universe_metadata(universe_path)
    changed = 0

    for path in sorted(cache_dir.glob("*.json")):
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)

        symbol = str(payload.get("symbol", path.stem)).strip().upper()
        metadata = universe.get(symbol)
        if not metadata:
            continue

        dirty = False
        for field in SYNC_FIELDS:
            value = metadata.get(field)
            if value is None:
                continue
            if payload.get(field) != value:
                payload[field] = value
                dirty = True

        if dirty:
            write_json_atomic(path, payload)
            changed += 1

    return changed


def main() -> int:
    changed = reconcile_cache_metadata()
    print(f"Reconciled universe metadata for {changed} stock cache(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
