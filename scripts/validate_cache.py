from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from core.settings import DCF_CACHE_DIR, MANIFEST_PATH, UNIVERSE_PATH
from core.universe import Stock, load_universe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate DCF cache files")
    parser.add_argument("--symbols", nargs="+")
    parser.add_argument(
        "--minimum-coverage",
        type=float,
        default=1.0,
        help="Required fraction of universe files, from 0 to 1",
    )
    parser.add_argument(
        "--allow-missing-price",
        action="store_true",
        help="Do not fail validation when current price is missing",
    )
    return parser.parse_args()


def validate_cache_entries(
    universe: list[Stock],
    manifest: dict[str, Any],
    cache_dir: Path,
    *,
    allow_missing_price: bool,
) -> tuple[int, int, dict[str, list[str]]]:
    valid_count = 0
    missing_count = 0
    issues: dict[str, list[str]] = {}

    for stock in universe:
        path = cache_dir / f"{stock.symbol}.json"
        entry = manifest.get("stocks", {}).get(stock.symbol)

        if not path.exists() or not entry:
            missing_count += 1
            continue

        try:
            with path.open(encoding="utf-8") as file:
                payload = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            issues[stock.symbol] = [f"invalid cache JSON: {error}"]
            continue

        stock_issues: list[str] = []
        if payload.get("symbol") != stock.symbol:
            stock_issues.append("symbol mismatch")
        if (
            payload.get("market_data", {}).get("price") is None
            and not allow_missing_price
        ):
            stock_issues.append("missing current price")
        if payload.get("market_data", {}).get("shares_outstanding") is None:
            stock_issues.append("missing shares outstanding")
        if not payload.get("annual"):
            stock_issues.append("missing annual financials")
        if not payload.get("valuation_bases"):
            stock_issues.append("missing valuation bases")

        if stock_issues:
            issues[stock.symbol] = stock_issues
        else:
            valid_count += 1

    return valid_count, missing_count, issues


def main() -> int:
    args = parse_args()
    universe = load_universe(UNIVERSE_PATH)
    if args.symbols:
        requested = {symbol.upper() for symbol in args.symbols}
        universe = [stock for stock in universe if stock.symbol in requested]
    with MANIFEST_PATH.open(encoding="utf-8") as file:
        manifest = json.load(file)

    valid_count, missing_count, issues = validate_cache_entries(
        universe,
        manifest,
        DCF_CACHE_DIR,
        allow_missing_price=args.allow_missing_price,
    )

    coverage = (
        valid_count / len(universe)
        if universe
        else 0
    )
    for symbol, stock_issues in sorted(issues.items()):
        for issue in stock_issues:
            print(f"WARNING: {symbol}: {issue}")

    errors: list[str] = []
    if coverage < args.minimum_coverage:
        errors.append(
            f"valid cache coverage {coverage:.1%} is below "
            f"{args.minimum_coverage:.1%}"
        )

    if errors:
        for error in errors:
            print(error)
        return 1

    print(
        f"Validated cache schema; valid coverage is "
        f"{valid_count}/{len(universe)} ({coverage:.1%}), "
        f"with {missing_count} missing and {len(issues)} incomplete cache(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
