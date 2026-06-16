from __future__ import annotations

import argparse
import sys

from core.cache import update_manifest, write_stock_cache
from core.settings import UNIVERSE_PATH
from core.universe import load_universe
from core.yfinance_client import fetch_stock


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update selected stock JSON caches")
    parser.add_argument(
        "--symbols",
        nargs="+",
        help="Only update these symbols (defaults to all enabled stocks)",
    )
    parser.add_argument(
        "--index",
        dest="index_id",
        help="Only update constituents of this index",
    )
    parser.add_argument("--shard-index", type=int, default=0)
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument(
        "--skip-manifest",
        action="store_true",
        help="Write stock files only; useful for parallel Action shards",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Return success when some symbols fail after recording failures",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
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
            print(f"Unknown or disabled symbols: {', '.join(missing)}", file=sys.stderr)
            return 2

    if args.shard_count <= 0 or not 0 <= args.shard_index < args.shard_count:
        print("Invalid shard configuration", file=sys.stderr)
        return 2
    stocks = [
        stock
        for position, stock in enumerate(sorted(stocks, key=lambda item: item.symbol))
        if position % args.shard_count == args.shard_index
    ]

    successes = []
    failures: dict[str, str] = {}

    for stock in stocks:
        print(f"Fetching {stock.symbol}...")
        try:
            payload = fetch_stock(stock)
            path = write_stock_cache(payload)
            successes.append(payload)
            print(
                f"Saved DCF snapshot as of "
                f"{payload['market_data']['as_of']} to {path}"
            )
        except Exception as error:
            failures[stock.symbol] = str(error)
            print(f"Failed {stock.symbol}: {error}", file=sys.stderr)

    if not args.skip_manifest:
        update_manifest(successes, failures)

    print(f"Updated {len(successes)} stock(s); {len(failures)} failed.")
    return 1 if failures and not args.allow_partial else 0


if __name__ == "__main__":
    raise SystemExit(main())
