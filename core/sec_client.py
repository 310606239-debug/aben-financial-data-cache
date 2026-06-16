from __future__ import annotations

import os
from typing import Any, Optional

import requests

from core.env import load_dotenv


SEC_BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts"

CONCEPTS = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "net_income": ("NetIncomeLoss",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_expenditure": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    ),
    "diluted_eps": ("EarningsPerShareDiluted",),
    "diluted_shares": ("WeightedAverageNumberOfDilutedSharesOutstanding",),
}

UNITS = {
    "revenue": "USD",
    "net_income": "USD",
    "operating_cash_flow": "USD",
    "capital_expenditure": "USD",
    "diluted_eps": "USD/shares",
    "diluted_shares": "shares",
}


def _annual_facts(
    facts: dict[str, Any],
    concepts: tuple[str, ...],
    unit: str,
) -> dict[str, dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    for concept in concepts:
        units = us_gaap.get(concept, {}).get("units", {})
        for item in units.get(unit, []):
            if item.get("form") not in ("10-K", "10-K/A", "20-F", "20-F/A"):
                continue
            if item.get("fp") != "FY" or not item.get("end"):
                continue
            candidates.append(item)
        if candidates:
            break

    by_end: dict[str, dict[str, Any]] = {}
    for item in sorted(candidates, key=lambda row: row.get("filed", "")):
        by_end[item["end"]] = item
    return by_end


def fetch_sec_annual(cik: str, timeout: int = 30) -> Optional[list[dict[str, Any]]]:
    load_dotenv()
    identity = os.getenv("SEC_USER_AGENT", "").strip()
    if not identity:
        return None

    response = requests.get(
        f"{SEC_BASE_URL}/CIK{cik.zfill(10)}.json",
        headers={
            "User-Agent": identity,
            "Accept-Encoding": "gzip, deflate",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    facts = response.json()

    series = {
        field: _annual_facts(facts, concepts, UNITS[field])
        for field, concepts in CONCEPTS.items()
    }
    ends = sorted(
        set().union(*(values.keys() for values in series.values())),
        reverse=True,
    )

    annual = []
    for end in ends:
        row = {"fiscal_year": end, "source": "sec-edgar"}
        for field, values in series.items():
            item = values.get(end)
            value = item.get("val") if item else None
            if field == "capital_expenditure" and value is not None:
                value = -abs(value)
            row[field] = value

        operating_cash_flow = row.get("operating_cash_flow")
        capital_expenditure = row.get("capital_expenditure")
        row["free_cash_flow"] = (
            operating_cash_flow + capital_expenditure
            if operating_cash_flow is not None
            and capital_expenditure is not None
            else None
        )
        annual.append(row)

    return annual
