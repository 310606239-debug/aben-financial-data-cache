from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.cache import write_json_atomic
from core.settings import CACHE_FAILURES_DIR, DCF_CACHE_DIR, MANIFEST_PATH, SCHEMA_VERSION


def load_previous_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {"stocks": {}}
    return payload if isinstance(payload, dict) else {"stocks": {}}


def load_failure_reports(path: Path | None = None) -> dict[str, str]:
    path = path or CACHE_FAILURES_DIR
    failures: dict[str, str] = {}
    for report_path in sorted(path.glob("*.json")):
        try:
            with report_path.open(encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError):
            continue
        for symbol, error in payload.get("failures", {}).items():
            failures[str(symbol).upper()] = str(error)
    return failures


def main() -> int:
    previous_manifest = load_previous_manifest()
    previous_stocks = previous_manifest.get("stocks", {})
    previous_stocks = previous_stocks if isinstance(previous_stocks, dict) else {}
    stocks = {}
    for path in sorted(DCF_CACHE_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
        if payload.get("schema_version") != SCHEMA_VERSION:
            continue
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
            "history_path": f"cache/history/dcf/{symbol}/",
        }

    failures = load_failure_reports()
    now = datetime.now(timezone.utc).isoformat()
    for symbol, error in failures.items():
        if symbol in stocks:
            continue
        previous = previous_stocks.get(symbol, {})
        previous = previous if isinstance(previous, dict) else {}
        stocks[symbol] = {
            **previous,
            "status": "error",
            "last_attempt_at": now,
            "error": error,
        }

    write_json_atomic(
        MANIFEST_PATH,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": now,
            "stocks": dict(sorted(stocks.items())),
        },
    )
    print(
        f"Rebuilt manifest for {len(stocks)} stock cache(s), "
        f"including {len(failures)} current failure report(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
