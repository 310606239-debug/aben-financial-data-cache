from __future__ import annotations

from typing import Optional


def forward_fair_value(
    *,
    base_per_share: float,
    growth_rate: float,
    projection_years: int,
    discount_rate: float,
    terminal_multiple: float,
    margin: float = 1.0,
) -> float:
    if projection_years <= 0:
        raise ValueError("projection_years must be positive")
    if base_per_share <= 0 or terminal_multiple <= 0 or margin <= 0:
        raise ValueError("valuation inputs must be positive")
    if discount_rate <= -1 or growth_rate <= -1:
        raise ValueError("rates must be greater than -100%")

    future_metric = base_per_share * (1 + growth_rate) ** projection_years
    future_price = future_metric * margin * terminal_multiple
    return future_price / (1 + discount_rate) ** projection_years


def reverse_implied_growth(
    *,
    current_price: float,
    base_per_share: float,
    projection_years: int,
    discount_rate: float,
    terminal_multiple: float,
    margin: float = 1.0,
) -> Optional[float]:
    if projection_years <= 0:
        raise ValueError("projection_years must be positive")
    if (
        current_price <= 0
        or base_per_share <= 0
        or terminal_multiple <= 0
        or margin <= 0
    ):
        return None
    if discount_rate <= -1:
        raise ValueError("discount_rate must be greater than -100%")

    required_growth_factor = (
        current_price
        * (1 + discount_rate) ** projection_years
        / (base_per_share * margin * terminal_multiple)
    )
    return required_growth_factor ** (1 / projection_years) - 1


def forecast_irr(
    *,
    current_price: float,
    future_price: float,
    projection_years: int,
) -> Optional[float]:
    if current_price <= 0 or future_price <= 0 or projection_years <= 0:
        return None
    return (future_price / current_price) ** (1 / projection_years) - 1
