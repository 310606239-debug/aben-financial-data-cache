from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Any, Optional, Union

import pandas as pd
import yfinance as yf

from core.metrics import (
    available_windows,
    historical_average,
    historical_growth,
    safe_ratio,
)
from core.sec_client import fetch_sec_annual
from core.settings import SCHEMA_VERSION
from core.universe import Stock


Number = Optional[Union[int, float]]


def _json_number(value: Any) -> Number:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def _date_string(value: Any) -> str:
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value)


def _series_value(frame: pd.DataFrame, names: list[str], column: Any) -> Any:
    if frame.empty or column not in frame.columns:
        return None
    for name in names:
        if name in frame.index:
            value = frame.at[name, column]
            if pd.notna(value):
                return value
    return None


def _latest_value(frame: pd.DataFrame, names: list[str]) -> Number:
    if frame.empty:
        return None
    for column in sorted(frame.columns, reverse=True):
        value = _series_value(frame, names, column)
        if value is not None:
            return _json_number(value)
    return None


def _latest_across(frames: list[pd.DataFrame], names: list[str]) -> Number:
    for frame in frames:
        value = _latest_value(frame, names)
        if value is not None:
            return value
    return None


def _sum_quarters(frame: pd.DataFrame, names: list[str]) -> Number:
    if frame.empty:
        return None
    values = []
    for column in sorted(frame.columns, reverse=True)[:4]:
        value = _series_value(frame, names, column)
        if value is None:
            return None
        values.append(float(value))
    return _json_number(sum(values)) if len(values) == 4 else None


def _free_cash_flow(frame: pd.DataFrame, column: Any) -> Number:
    direct = _series_value(frame, ["Free Cash Flow"], column)
    if direct is not None:
        return _json_number(direct)
    operating = _series_value(
        frame,
        ["Operating Cash Flow", "Total Cash From Operating Activities"],
        column,
    )
    capital_expenditure = _series_value(
        frame,
        ["Capital Expenditure", "Capital Expenditures"],
        column,
    )
    if operating is None or capital_expenditure is None:
        return None
    return _json_number(float(operating) + float(capital_expenditure))


def _sum_quarterly_fcf(frame: pd.DataFrame) -> Number:
    if frame.empty:
        return None
    columns = sorted(frame.columns, reverse=True)[:4]
    values = [_free_cash_flow(frame, column) for column in columns]
    if len(values) != 4 or any(value is None for value in values):
        return None
    return _json_number(sum(float(value) for value in values if value is not None))


def _build_yfinance_annual(
    income: pd.DataFrame,
    cashflow: pd.DataFrame,
) -> list[dict[str, Any]]:
    columns = sorted(set(income.columns).union(cashflow.columns), reverse=True)
    annual = []
    for column in columns:
        revenue = _json_number(_series_value(income, ["Total Revenue"], column))
        net_income = _json_number(
            _series_value(
                income,
                ["Net Income", "Net Income Common Stockholders"],
                column,
            )
        )
        diluted_eps = _json_number(_series_value(income, ["Diluted EPS"], column))
        diluted_shares = _json_number(
            _series_value(
                income,
                ["Diluted Average Shares", "Basic Average Shares"],
                column,
            )
        )
        operating_cash_flow = _json_number(
            _series_value(
                cashflow,
                ["Operating Cash Flow", "Total Cash From Operating Activities"],
                column,
            )
        )
        capital_expenditure = _json_number(
            _series_value(
                cashflow,
                ["Capital Expenditure", "Capital Expenditures"],
                column,
            )
        )
        free_cash_flow = _free_cash_flow(cashflow, column)
        row = {
            "fiscal_year": _date_string(column),
            "source": "yfinance",
            "revenue": revenue,
            "net_income": net_income,
            "diluted_eps": diluted_eps,
            "diluted_shares": diluted_shares,
            "operating_cash_flow": operating_cash_flow,
            "capital_expenditure": capital_expenditure,
            "free_cash_flow": free_cash_flow,
        }
        if any(value is not None for key, value in row.items() if key not in ("fiscal_year", "source")):
            annual.append(row)
    return annual


def _merge_annual(
    primary: Optional[list[dict[str, Any]]],
    fallback: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {
        row["fiscal_year"][:4]: dict(row) for row in fallback
    }
    for primary_row in primary or []:
        year = primary_row["fiscal_year"][:4]
        merged = rows.get(year, {"fiscal_year": primary_row["fiscal_year"]})
        for key, value in primary_row.items():
            if value is not None:
                merged[key] = value
        rows[year] = merged
    return [rows[year] for year in sorted(rows, reverse=True)[:12]]


def _attach_derived_fields(
    annual: list[dict[str, Any]],
    prices: pd.DataFrame,
) -> None:
    sorted_prices = prices.sort_index() if not prices.empty else prices
    for row in annual:
        shares = row.get("diluted_shares")
        row["revenue_per_share"] = safe_ratio(row.get("revenue"), shares)
        row["free_cash_flow_per_share"] = safe_ratio(
            row.get("free_cash_flow"), shares
        )
        row["net_margin"] = safe_ratio(row.get("net_income"), row.get("revenue"))
        row["cash_conversion"] = safe_ratio(
            row.get("free_cash_flow"), row.get("net_income")
        )

        year_end_price = None
        if not sorted_prices.empty:
            fiscal_end = pd.Timestamp(row["fiscal_year"])
            eligible = sorted_prices[sorted_prices.index.tz_localize(None) <= fiscal_end]
            if not eligible.empty:
                year_end_price = _json_number(eligible.iloc[-1].get("Close"))
        row["year_end_price"] = year_end_price
        row["price_to_earnings"] = safe_ratio(
            year_end_price, row.get("diluted_eps")
        )
        row["price_to_fcf"] = safe_ratio(
            year_end_price, row.get("free_cash_flow_per_share")
        )


def _latest_positive_base(
    ttm: Number,
    annual: list[dict[str, Any]],
    field: str,
) -> tuple[Number, Optional[str]]:
    if ttm is not None:
        return ttm, "ttm"
    for row in annual:
        if row.get(field) is not None:
            return row[field], row["fiscal_year"]
    return None, None


def fetch_stock(stock: Stock, *, attempts: int = 3) -> dict[str, Any]:
    last_error: Optional[Exception] = None

    for attempt in range(1, attempts + 1):
        try:
            ticker = yf.Ticker(stock.symbol)
            price_frame = ticker.history(
                period="10y",
                interval="1d",
                auto_adjust=False,
                actions=False,
                raise_errors=True,
            )
            if price_frame.empty:
                raise RuntimeError("yfinance returned no current price")

            income_annual = ticker.income_stmt
            income_quarterly = ticker.quarterly_income_stmt
            balance_quarterly = ticker.quarterly_balance_sheet
            balance_annual = ticker.balance_sheet
            cashflow_annual = ticker.cash_flow
            cashflow_quarterly = ticker.quarterly_cash_flow

            latest_price_row = price_frame.sort_index().iloc[-1]
            latest_price_date = price_frame.sort_index().index[-1]
            price = _json_number(latest_price_row.get("Close"))

            shares = _latest_across(
                [balance_quarterly, balance_annual],
                ["Ordinary Shares Number", "Share Issued"],
            )
            if shares is None:
                shares = _latest_value(
                    income_quarterly,
                    ["Diluted Average Shares", "Basic Average Shares"],
                )

            revenue_ttm = _sum_quarters(income_quarterly, ["Total Revenue"])
            net_income_ttm = _sum_quarters(
                income_quarterly,
                ["Net Income", "Net Income Common Stockholders"],
            )
            diluted_eps_ttm = _sum_quarters(income_quarterly, ["Diluted EPS"])
            fcf_ttm = _sum_quarterly_fcf(cashflow_quarterly)
            operating_cash_flow_ttm = _sum_quarters(
                cashflow_quarterly,
                ["Operating Cash Flow", "Total Cash From Operating Activities"],
            )
            capital_expenditure_ttm = _sum_quarters(
                cashflow_quarterly,
                ["Capital Expenditure", "Capital Expenditures"],
            )

            yfinance_annual = _build_yfinance_annual(
                income_annual, cashflow_annual
            )
            sec_annual = None
            warnings = []
            sources = ["yfinance"]
            if stock.market == "US" and stock.cik:
                try:
                    sec_annual = fetch_sec_annual(stock.cik)
                    if sec_annual:
                        sources.insert(0, "sec-edgar")
                    else:
                        warnings.append(
                            "SEC_USER_AGENT is not configured; using yfinance financials"
                        )
                except Exception as error:
                    warnings.append(f"SEC fallback unavailable: {error}")

            annual = _merge_annual(sec_annual, yfinance_annual)
            _attach_derived_fields(annual, price_frame)

            revenue_base, revenue_period = _latest_positive_base(
                revenue_ttm, annual, "revenue"
            )
            earnings_base, earnings_period = _latest_positive_base(
                net_income_ttm, annual, "net_income"
            )
            fcf_base, fcf_period = _latest_positive_base(
                fcf_ttm, annual, "free_cash_flow"
            )

            cash = _latest_across(
                [balance_quarterly, balance_annual],
                [
                    "Cash Cash Equivalents And Short Term Investments",
                    "Cash And Cash Equivalents",
                    "Cash Financial",
                ],
            )
            debt = _latest_across(
                [balance_quarterly, balance_annual],
                ["Total Debt"],
            )
            market_cap = (
                _json_number(float(price) * float(shares))
                if price is not None and shares is not None
                else None
            )

            if len(annual) < 5:
                warnings.append("fewer than 5 annual financial periods are available")
            if shares is None:
                warnings.append("shares outstanding is unavailable")

            return {
                "schema_version": SCHEMA_VERSION,
                "symbol": stock.symbol,
                "name": stock.name,
                "exchange": stock.exchange,
                "currency": stock.currency,
                "market": stock.market,
                "indexes": list(stock.indexes),
                "sources": sources,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "market_data": {
                    "as_of": _date_string(latest_price_date),
                    "price": price,
                    "shares_outstanding": shares,
                    "market_cap": market_cap,
                    "cash_and_short_term_investments": cash,
                    "total_debt": debt,
                    "enterprise_value": (
                        _json_number(
                            float(market_cap) + float(debt or 0) - float(cash or 0)
                        )
                        if market_cap is not None
                        else None
                    ),
                },
                "ttm": {
                    "revenue": revenue_ttm,
                    "net_income": net_income_ttm,
                    "diluted_eps": diluted_eps_ttm,
                    "free_cash_flow": fcf_ttm,
                    "operating_cash_flow": operating_cash_flow_ttm,
                    "capital_expenditure": capital_expenditure_ttm,
                    "revenue_per_share": safe_ratio(revenue_ttm, shares),
                    "free_cash_flow_per_share": safe_ratio(fcf_ttm, shares),
                    "net_margin": safe_ratio(net_income_ttm, revenue_ttm),
                    "cash_conversion": safe_ratio(fcf_ttm, net_income_ttm),
                },
                "valuation_bases": {
                    "revenue": {
                        "value": revenue_base,
                        "period": revenue_period,
                        "per_share": safe_ratio(revenue_base, shares),
                    },
                    "earnings": {
                        "value": earnings_base,
                        "period": earnings_period,
                        "per_share": (
                            diluted_eps_ttm
                            if earnings_period == "ttm" and diluted_eps_ttm is not None
                            else safe_ratio(earnings_base, shares)
                        ),
                    },
                    "free_cash_flow": {
                        "value": fcf_base,
                        "period": fcf_period,
                        "per_share": safe_ratio(fcf_base, shares),
                    },
                },
                "annual": annual,
                "historical_metrics": {
                    "available_growth_windows": {
                        "revenue": available_windows(annual, "revenue"),
                        "earnings": available_windows(annual, "net_income"),
                        "free_cash_flow": available_windows(
                            annual, "free_cash_flow"
                        ),
                    },
                    "growth": {
                        "revenue": historical_growth(annual, "revenue"),
                        "earnings": historical_growth(annual, "net_income"),
                        "free_cash_flow": historical_growth(
                            annual, "free_cash_flow"
                        ),
                    },
                    "averages": {
                        "net_margin": historical_average(annual, "net_margin"),
                        "cash_conversion": historical_average(
                            annual, "cash_conversion"
                        ),
                        "price_to_earnings": historical_average(
                            annual, "price_to_earnings"
                        ),
                        "price_to_fcf": historical_average(
                            annual, "price_to_fcf"
                        ),
                    },
                },
                "calculator_contract": {
                    "forward_models": {
                        "revenue_growth": {
                            "base": "valuation_bases.revenue.per_share",
                            "margin": "user_input.net_margin",
                            "terminal_multiple": "user_input.terminal_pe",
                        },
                        "earnings_growth": {
                            "base": "valuation_bases.earnings.per_share",
                            "terminal_multiple": "user_input.terminal_pe",
                        },
                        "fcf_growth": {
                            "base": "valuation_bases.free_cash_flow.per_share",
                            "terminal_multiple": "user_input.terminal_price_to_fcf",
                        },
                    },
                    "common_user_inputs": [
                        "projection_years",
                        "growth_rate",
                        "discount_rate",
                    ],
                    "forward_output": "fair_value_per_share",
                    "reverse_output": "implied_compound_growth_rate",
                },
                "data_quality": {"warnings": warnings},
            }
        except Exception as error:
            last_error = error
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))

    raise RuntimeError(
        f"Failed to fetch {stock.symbol} after {attempts} attempts: {last_error}"
    ) from last_error
