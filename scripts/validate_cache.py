from __future__ import annotations

import argparse
import json

from core.settings import DCF_CACHE_DIR, MANIFEST_PATH, UNIVERSE_PATH
from core.universe import load_universe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate DCF cache files")
    parser.add_argument("--symbols", nargs="+")
    parser.add_argument(
        "--minimum-coverage",
        type=float,
        default=1.0,
        help="Required fraction of universe files, from 0 to 1",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    universe = load_universe(UNIVERSE_PATH)
    if args.symbols:
        requested = {symbol.upper() for symbol in args.symbols}
        universe = [stock for stock in universe if stock.symbol in requested]
    with MANIFEST_PATH.open(encoding="utf-8") as file:
        manifest = json.load(file)

    errors: list[str] = []
    missing_count = 0
    for stock in universe:
        path = DCF_CACHE_DIR / f"{stock.symbol}.json"
        entry = manifest.get("stocks", {}).get(stock.symbol)

        if not path.exists():
            missing_count += 1
            continue
        if not entry:
            missing_count += 1
            continue

        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
        if payload.get("symbol") != stock.symbol:
            errors.append(f"{stock.symbol}: symbol mismatch")
        if payload.get("market_data", {}).get("price") is None:
            errors.append(f"{stock.symbol}: missing current price")
        if payload.get("market_data", {}).get("shares_outstanding") is None:
            errors.append(f"{stock.symbol}: missing shares outstanding")
        if not payload.get("annual"):
            errors.append(f"{stock.symbol}: missing annual financials")
        if not payload.get("valuation_bases"):
            errors.append(f"{stock.symbol}: missing valuation bases")

    coverage = (
        (len(universe) - missing_count) / len(universe)
        if universe
        else 0
    )
    if coverage < args.minimum_coverage:
        errors.append(
            f"cache coverage {coverage:.1%} is below "
            f"{args.minimum_coverage:.1%}"
        )

    if errors:
        for error in errors:
            print(error)
        return 1

    print(
        f"Validated cache schema; coverage is "
        f"{len(universe) - missing_count}/{len(universe)} ({coverage:.1%})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
