from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Stock:
    symbol: str
    name: str
    exchange: str
    currency: str
    market: str
    indexes: tuple[str, ...]
    cik: Optional[str] = None


def load_universe(path: Path) -> list[Stock]:
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)

    if payload.get("schema_version") not in (1, 2):
        raise ValueError(f"Unsupported universe schema in {path}")

    stocks: list[Stock] = []
    seen: set[str] = set()

    for index, item in enumerate(payload.get("stocks", [])):
        if not item.get("enabled", True):
            continue

        symbol = str(item.get("symbol", "")).strip().upper()
        if not symbol:
            raise ValueError(f"Missing symbol at stocks[{index}]")
        if symbol in seen:
            raise ValueError(f"Duplicate symbol in universe: {symbol}")

        seen.add(symbol)
        stocks.append(
            Stock(
                symbol=symbol,
                name=str(item.get("name", symbol)).strip(),
                exchange=str(item.get("exchange", "")).strip(),
                currency=str(item.get("currency", "")).strip(),
                market=str(item.get("market", "US")).strip().upper(),
                indexes=tuple(sorted(item.get("indexes", []))),
                cik=(
                    str(item["cik"]).strip().zfill(10)
                    if item.get("cik") not in (None, "")
                    else None
                ),
            )
        )

    if not stocks:
        raise ValueError("Universe contains no enabled stocks")

    return stocks
