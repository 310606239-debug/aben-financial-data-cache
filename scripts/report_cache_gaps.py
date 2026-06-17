from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.cache import write_json_atomic
from core.settings import (
    CACHE_REPORTS_DIR,
    DCF_CACHE_DIR,
    MANIFEST_PATH,
    UNIVERSE_PATH,
)
from core.universe import Stock, load_universe


DEFAULT_REPORT_PATH = CACHE_REPORTS_DIR / "cache_gaps.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report cache coverage gaps")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Path to write the JSON coverage report.",
    )
    return parser.parse_args()


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {"stocks": {}}
    return payload if isinstance(payload, dict) else {"stocks": {}}


def _increment_indexes(counter: Counter[str], stock: Stock) -> None:
    for index_id in stock.indexes:
        counter[index_id] += 1


def _sample_append(samples: list[dict[str, Any]], row: dict[str, Any], limit: int) -> None:
    if len(samples) < limit:
        samples.append(row)


def build_cache_gap_report(
    *,
    universe_path: Path = UNIVERSE_PATH,
    cache_dir: Path = DCF_CACHE_DIR,
    manifest_path: Path = MANIFEST_PATH,
    sample_limit: int = 200,
) -> dict[str, Any]:
    universe = load_universe(universe_path)
    manifest = load_manifest(manifest_path)
    manifest_stocks = manifest.get("stocks", {})
    manifest_stocks = manifest_stocks if isinstance(manifest_stocks, dict) else {}

    totals_by_market: Counter[str] = Counter()
    cached_by_market: Counter[str] = Counter()
    missing_by_market: Counter[str] = Counter()
    error_by_market: Counter[str] = Counter()
    totals_by_index: Counter[str] = Counter()
    cached_by_index: Counter[str] = Counter()
    missing_by_index: Counter[str] = Counter()
    error_by_index: Counter[str] = Counter()

    missing_samples: list[dict[str, Any]] = []
    error_samples: list[dict[str, Any]] = []
    quality_samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    quality_counts: Counter[str] = Counter()

    cached_count = 0
    missing_count = 0
    error_count = 0

    for stock in universe:
        totals_by_market[stock.market] += 1
        _increment_indexes(totals_by_index, stock)

        path = cache_dir / f"{stock.symbol}.json"
        entry = manifest_stocks.get(stock.symbol, {})
        entry = entry if isinstance(entry, dict) else {}

        if entry.get("status") == "error":
            error_count += 1
            error_by_market[stock.market] += 1
            _increment_indexes(error_by_index, stock)
            _sample_append(
                error_samples,
                {
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "market": stock.market,
                    "indexes": list(stock.indexes),
                    "error": entry.get("error"),
                },
                sample_limit,
            )

        if not path.exists():
            missing_count += 1
            missing_by_market[stock.market] += 1
            _increment_indexes(missing_by_index, stock)
            _sample_append(
                missing_samples,
                {
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "market": stock.market,
                    "indexes": list(stock.indexes),
                    "manifest_status": entry.get("status"),
                },
                sample_limit,
            )
            continue

        cached_count += 1
        cached_by_market[stock.market] += 1
        _increment_indexes(cached_by_index, stock)

        try:
            with path.open(encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            quality_counts["unreadable_cache"] += 1
            _sample_append(
                quality_samples["unreadable_cache"],
                {"symbol": stock.symbol, "error": str(error)},
                sample_limit,
            )
            continue

        checks = {
            "missing_price": payload.get("market_data", {}).get("price") is None,
            "missing_shares": payload.get("market_data", {}).get("shares_outstanding") is None,
            "missing_annual": not payload.get("annual"),
            "missing_valuation_bases": not payload.get("valuation_bases"),
            "short_annual_history": len(payload.get("annual") or []) < 5,
        }
        for issue, present in checks.items():
            if not present:
                continue
            quality_counts[issue] += 1
            _sample_append(
                quality_samples[issue],
                {
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "market": stock.market,
                    "indexes": list(stock.indexes),
                },
                sample_limit,
            )

    total = len(universe)
    coverage = cached_count / total if total else 0
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "universe_count": total,
            "cached_count": cached_count,
            "missing_count": missing_count,
            "error_count": error_count,
            "coverage": coverage,
        },
        "by_market": {
            market: {
                "universe": totals_by_market[market],
                "cached": cached_by_market[market],
                "missing": missing_by_market[market],
                "errors": error_by_market[market],
            }
            for market in sorted(totals_by_market)
        },
        "by_index": {
            index_id: {
                "universe": totals_by_index[index_id],
                "cached": cached_by_index[index_id],
                "missing": missing_by_index[index_id],
                "errors": error_by_index[index_id],
            }
            for index_id in sorted(totals_by_index)
        },
        "quality_counts": dict(sorted(quality_counts.items())),
        "samples": {
            "missing": missing_samples,
            "errors": error_samples,
            "quality": {
                issue: rows
                for issue, rows in sorted(quality_samples.items())
            },
        },
    }


def main() -> int:
    args = parse_args()
    report = build_cache_gap_report()
    write_json_atomic(args.output, report)
    summary = report["summary"]
    print(
        "Cache coverage report: "
        f"{summary['cached_count']}/{summary['universe_count']} "
        f"({summary['coverage']:.1%}), "
        f"{summary['missing_count']} missing, {summary['error_count']} errors."
    )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
