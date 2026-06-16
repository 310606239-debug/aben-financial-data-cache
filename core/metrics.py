from __future__ import annotations

from typing import Any, Optional


def safe_ratio(numerator: Any, denominator: Any) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def cagr(current: Any, previous: Any, years: int) -> Optional[float]:
    if (
        current is None
        or previous is None
        or years <= 0
        or float(current) <= 0
        or float(previous) <= 0
    ):
        return None
    return (float(current) / float(previous)) ** (1 / years) - 1


def historical_growth(
    annual: list[dict[str, Any]],
    field: str,
    windows: tuple[int, ...] = (1, 3, 5, 10),
) -> dict[str, Optional[float]]:
    values = [row.get(field) for row in annual if row.get(field) is not None]
    result: dict[str, Optional[float]] = {}
    for years in windows:
        result[f"{years}y"] = (
            cagr(values[0], values[years], years)
            if len(values) > years
            else None
        )
    return result


def historical_average(
    annual: list[dict[str, Any]],
    field: str,
    windows: tuple[int, ...] = (1, 3, 5, 10),
) -> dict[str, Optional[float]]:
    values = [row.get(field) for row in annual if row.get(field) is not None]
    result: dict[str, Optional[float]] = {}
    for years in windows:
        sample = values[:years] if len(values) >= years else []
        result[f"{years}y"] = (
            sum(float(value) for value in sample) / len(sample)
            if sample
            else None
        )
    return result


def available_windows(
    annual: list[dict[str, Any]],
    field: str,
    windows: tuple[int, ...] = (1, 3, 5, 10),
) -> list[int]:
    count = sum(row.get(field) is not None for row in annual)
    return [years for years in windows if count > years]
