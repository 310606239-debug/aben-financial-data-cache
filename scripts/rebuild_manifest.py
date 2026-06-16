from __future__ import annotations

import json
from datetime import datetime, timezone

from core.cache import write_json_atomic
from core.settings import DCF_CACHE_DIR, MANIFEST_PATH, SCHEMA_VERSION


def main() -> int:
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
        }

    write_json_atomic(
        MANIFEST_PATH,
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stocks": stocks,
        },
    )
    print(f"Rebuilt manifest for {len(stocks)} stock cache(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
