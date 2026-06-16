from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import yfinance as yf

from core.cache import write_json_atomic
from core.settings import DCF_CACHE_DIR, UNIVERSE_PATH
from core.universe import load_universe


def _latest_close(frame: pd.DataFrame, symbol: str, multiple: bool):
    if multiple:
        if symbol not in frame.columns.get_level_values(0):
            return None
        prices = frame[symbol]["Close"].dropna()
    else:
        prices = frame["Close"].dropna()
    if prices.empty:
        return None
    return prices.index[-1], float(prices.iloc[-1])


def main() -> int:
    universe = load_universe(UNIVERSE_PATH)
    existing = {
        stock.symbol: stock
        for stock in universe
        if (DCF_CACHE_DIR / f"{stock.symbol}.json").exists()
    }
    updated = 0

    symbols = sorted(existing)
    for start in range(0, len(symbols), 100):
        chunk = symbols[start : start + 100]
        frame = yf.download(
            tickers=chunk,
            period="5d",
            interval="1d",
            auto_adjust=False,
            actions=False,
            group_by="ticker",
            threads=True,
            progress=False,
        )
        multiple = len(chunk) > 1

        for symbol in chunk:
            latest = _latest_close(frame, symbol, multiple)
            if latest is None:
                continue
            timestamp, price = latest
            path = DCF_CACHE_DIR / f"{symbol}.json"
            with path.open(encoding="utf-8") as file:
                payload = json.load(file)

            market = payload["market_data"]
            market["price"] = price
            market["as_of"] = timestamp.date().isoformat()
            shares = market.get("shares_outstanding")
            if shares is not None:
                market_cap = price * float(shares)
                market["market_cap"] = market_cap
                market["enterprise_value"] = (
                    market_cap
                    + float(market.get("total_debt") or 0)
                    - float(market.get("cash_and_short_term_investments") or 0)
                )
            payload["price_refreshed_at"] = datetime.now(timezone.utc).isoformat()
            write_json_atomic(path, payload)
            updated += 1

    print(f"Updated current prices for {updated} cached securities.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
