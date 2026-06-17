from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

from core.cache import update_manifest, write_json_atomic, write_stock_cache
from core.metrics import available_windows, historical_average, historical_growth, safe_ratio
from core.sec_client import fetch_sec_annual
from core.settings import CACHE_FAILURES_DIR, DCF_CACHE_DIR, UNIVERSE_PATH
from core.update_policy import UpdatePolicy, load_manifest_status, select_refresh_candidates
from core.universe import Stock, load_universe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh US annual financial history from SEC without yfinance",
    )
    parser.add_argument("--symbols", nargs="+", help="Only update these symbols")
    parser.add_argument("--index", dest="index_id", help="Only update one index")
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--skip-manifest", action="store_true")
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument(
        "--stale-days",
        type=int,
        help="Only refresh SEC history for caches older than this many days.",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Only refresh SEC history for missing cache files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refresh selected SEC histories even when cache is fresh.",
    )
    return parser.parse_args()


def select_stocks(args: argparse.Namespace) -> list[Stock]:
    stocks = load_universe(UNIVERSE_PATH)

    if args.index_id:
        stocks = [
            stock for stock in stocks if args.index_id.lower() in stock.indexes
        ]

    if args.symbols:
        requested = {symbol.upper() for symbol in args.symbols}
        stocks = [stock for stock in stocks if stock.symbol in requested]
        found = {stock.symbol for stock in stocks}
        missing = sorted(requested - found)
        if missing:
            raise ValueError(f"Unknown or disabled symbols: {', '.join(missing)}")

    if args.shard_count <= 0 or not 0 <= args.shard_index < args.shard_count:
        raise ValueError("Invalid shard configuration")

    stocks = select_refresh_candidates(
        stocks,
        UpdatePolicy(
            force=args.force,
            missing_only=args.missing_only,
            stale_days=args.stale_days,
        ),
        load_manifest_status(),
    )

    return [
        stock
        for position, stock in enumerate(sorted(stocks, key=lambda item: item.symbol))
        if position % args.shard_count == args.shard_index
    ]


def load_existing_payload(symbol: str) -> dict[str, Any]:
    path = DCF_CACHE_DIR / f"{symbol}.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} does not exist; run update_cache first")
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def merge_sec_annual(
    existing: list[dict[str, Any]],
    sec_annual: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = {row["fiscal_year"][:4]: dict(row) for row in existing}

    for sec_row in sec_annual:
        year = sec_row["fiscal_year"][:4]
        merged = rows.get(year, {"fiscal_year": sec_row["fiscal_year"]})
        year_end_price = merged.get("year_end_price")

        for key, value in sec_row.items():
            if value is not None:
                merged[key] = value

        shares = merged.get("diluted_shares")
        merged["revenue_per_share"] = safe_ratio(merged.get("revenue"), shares)
        merged["free_cash_flow_per_share"] = safe_ratio(
            merged.get("free_cash_flow"), shares
        )
        merged["net_margin"] = safe_ratio(
            merged.get("net_income"), merged.get("revenue")
        )
        merged["cash_conversion"] = safe_ratio(
            merged.get("free_cash_flow"), merged.get("net_income")
        )
        merged["year_end_price"] = year_end_price
        merged["price_to_earnings"] = safe_ratio(
            year_end_price, merged.get("diluted_eps")
        )
        merged["price_to_fcf"] = safe_ratio(
            year_end_price, merged.get("free_cash_flow_per_share")
        )
        rows[year] = merged

    return [rows[year] for year in sorted(rows, reverse=True)]


def refresh_payload(stock: Stock) -> dict[str, Any]:
    if stock.market != "US" or not stock.cik:
        raise ValueError("SEC refresh only supports US stocks with CIK")

    payload = load_existing_payload(stock.symbol)
    sec_annual = fetch_sec_annual(stock.cik)
    if not sec_annual:
        raise RuntimeError("SEC returned no annual facts")

    annual = merge_sec_annual(payload.get("annual", []), sec_annual)
    sources = payload.setdefault("sources", [])
    if "sec-edgar" not in sources:
        sources.insert(0, "sec-edgar")
    if "yfinance" not in sources:
        sources.append("yfinance")

    payload["fetched_at"] = datetime.now(timezone.utc).isoformat()
    payload["annual"] = annual
    payload["historical_metrics"] = {
        "available_growth_windows": {
            "revenue": available_windows(annual, "revenue"),
            "earnings": available_windows(annual, "net_income"),
            "free_cash_flow": available_windows(annual, "free_cash_flow"),
        },
        "growth": {
            "revenue": historical_growth(annual, "revenue"),
            "earnings": historical_growth(annual, "net_income"),
            "free_cash_flow": historical_growth(annual, "free_cash_flow"),
        },
        "averages": {
            "net_margin": historical_average(annual, "net_margin"),
            "cash_conversion": historical_average(annual, "cash_conversion"),
            "price_to_earnings": historical_average(annual, "price_to_earnings"),
            "price_to_fcf": historical_average(annual, "price_to_fcf"),
        },
    }
    warnings = payload.setdefault("data_quality", {}).setdefault("warnings", [])
    payload["data_quality"]["warnings"] = [
        warning for warning in warnings if "SEC" not in warning
    ]
    return payload


def main() -> int:
    args = parse_args()
    try:
        stocks = select_stocks(args)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    successes = []
    failures: dict[str, str] = {}
    for stock in stocks:
        if stock.market != "US" or not stock.cik:
            continue
        print(f"Refreshing SEC annuals for {stock.symbol}...")
        try:
            payload = refresh_payload(stock)
            path = write_stock_cache(payload)
            successes.append(payload)
            print(f"Saved SEC-enhanced snapshot to {path}")
        except Exception as error:
            failures[stock.symbol] = str(error)
            print(f"Failed {stock.symbol}: {error}", file=sys.stderr)

    if args.skip_manifest and failures:
        write_json_atomic(
            CACHE_FAILURES_DIR / f"update_sec_cache_shard_{args.shard_index}.json",
            {
                "source": "update_sec_cache",
                "shard_index": args.shard_index,
                "shard_count": args.shard_count,
                "failures": failures,
            },
        )

    if not args.skip_manifest:
        update_manifest(successes, failures)

    print(f"Updated {len(successes)} stock(s); {len(failures)} failed.")
    return 1 if failures and not args.allow_partial else 0


if __name__ == "__main__":
    raise SystemExit(main())
