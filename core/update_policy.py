from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from core.settings import DCF_CACHE_DIR, MANIFEST_PATH
from core.universe import Stock


@dataclass(frozen=True)
class UpdatePolicy:
    force: bool = False
    missing_only: bool = False
    stale_days: Optional[int] = None
    retry_errors: bool = True


def parse_datetime(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_manifest_status(path: Path = MANIFEST_PATH) -> dict[str, dict[str, Any]]:
    try:
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    stocks = payload.get("stocks", {})
    return stocks if isinstance(stocks, dict) else {}


def stock_cache_exists(symbol: str) -> bool:
    return (DCF_CACHE_DIR / f"{symbol}.json").exists()


def should_refresh_stock(
    stock: Stock,
    policy: UpdatePolicy,
    manifest_status: dict[str, dict[str, Any]],
    *,
    now: Optional[datetime] = None,
) -> bool:
    if policy.force:
        return True

    exists = stock_cache_exists(stock.symbol)
    if not exists:
        return True

    status = manifest_status.get(stock.symbol, {})
    if policy.retry_errors and status.get("status") == "error":
        return True

    if policy.missing_only:
        return False

    if policy.stale_days is None:
        return True

    fetched_at = parse_datetime(status.get("fetched_at"))
    if fetched_at is None:
        return True

    now = now or datetime.now(timezone.utc)
    return fetched_at <= now - timedelta(days=policy.stale_days)


def select_refresh_candidates(
    stocks: Iterable[Stock],
    policy: UpdatePolicy,
    manifest_status: Optional[dict[str, dict[str, Any]]] = None,
) -> list[Stock]:
    status = manifest_status if manifest_status is not None else load_manifest_status()
    return [
        stock
        for stock in stocks
        if should_refresh_stock(stock, policy, status)
    ]
