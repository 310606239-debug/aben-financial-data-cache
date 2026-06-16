from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import yfinance as yf

from core.cache import write_json_atomic
from core.settings import DCF_CACHE_DIR, PRICE_HISTORY_DIR, UNIVERSE_PATH
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


def _json_number(value: Any):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not pd.notna(number):
        return None
    return int(number) if number.is_integer() else number


def _fast_info_value(fast_info: Any, key: str):
    try:
        return fast_info.get(key)
    except AttributeError:
        try:
            return fast_info[key]
        except (KeyError, TypeError):
            return None


def _refresh_chunk_shares(symbols: list[str]) -> dict[str, int | float]:
    refreshed: dict[str, int | float] = {}
    try:
        tickers = yf.Tickers(" ".join(symbols))
    except Exception:
        return refreshed

    for symbol in symbols:
        ticker = tickers.tickers.get(symbol)
        if ticker is None:
            continue
        try:
            shares = _json_number(_fast_info_value(ticker.fast_info, "shares"))
        except Exception:
            continue
        if shares is not None:
            refreshed[symbol] = shares
    return refreshed


def main() -> int:
    universe = load_universe(UNIVERSE_PATH)
    existing = {
        stock.symbol: stock
        for stock in universe
        if (DCF_CACHE_DIR / f"{stock.symbol}.json").exists()
    }
    updated = 0
    price_history: dict[str, dict] = {}

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
        refreshed_shares = _refresh_chunk_shares(chunk)

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
            shares = refreshed_shares.get(symbol, market.get("shares_outstanding"))
            if shares is not None:
                market["shares_outstanding"] = shares
                market["shares_source"] = (
                    "yfinance.fast_info"
                    if symbol in refreshed_shares
                    else market.get("shares_source")
                )
                market["shares_kind"] = "current_shares_outstanding"
                market["shares_refreshed_at"] = datetime.now(timezone.utc).isoformat()
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
            price_history[symbol] = {
                "symbol": symbol,
                "as_of": timestamp.date().isoformat(),
                "price": price,
                "shares_outstanding": shares,
                "market_cap": market.get("market_cap"),
                "currency": payload.get("currency"),
                "market": payload.get("market"),
            }
            updated += 1

    if price_history:
        today = datetime.now(timezone.utc).date().isoformat()
        history_path = PRICE_HISTORY_DIR / f"{today}.json"
        existing_history = {}
        if history_path.exists():
            with history_path.open(encoding="utf-8") as file:
                existing_history = json.load(file).get("prices", {})
        existing_history.update(price_history)
        write_json_atomic(
            history_path,
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "prices": dict(sorted(existing_history.items())),
            },
        )

    print(f"Updated current prices for {updated} cached securities.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
