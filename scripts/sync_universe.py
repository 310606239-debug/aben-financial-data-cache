from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from core.cache import write_json_atomic
from core.settings import INDEX_UNIVERSE_DIR, UNIVERSE_PATH


SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
QQQ_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
CSI300_URL = (
    "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/"
    "file/autofile/cons/000300cons.xls"
)

HSTECH_CONSTITUENTS = [
    ("00020", "SenseTime"),
    ("00241", "Alibaba Health"),
    ("00268", "Kingdee International"),
    ("00285", "BYD Electronic"),
    ("00300", "Midea Group"),
    ("00522", "ASMPT"),
    ("00700", "Tencent"),
    ("00780", "Tongcheng Travel"),
    ("00981", "SMIC"),
    ("00992", "Lenovo"),
    ("01024", "Kuaishou"),
    ("01211", "BYD"),
    ("01347", "Hua Hong Semiconductor"),
    ("01698", "Tencent Music"),
    ("01810", "Xiaomi"),
    ("02015", "Li Auto"),
    ("02382", "Sunny Optical"),
    ("03690", "Meituan"),
    ("03888", "Kingsoft"),
    ("06618", "JD Health"),
    ("06690", "Haier Smart Home"),
    ("09618", "JD.com"),
    ("09660", "Horizon Robotics"),
    ("09626", "Bilibili"),
    ("09866", "NIO"),
    ("09868", "XPeng"),
    ("09888", "Baidu"),
    ("09988", "Alibaba"),
    ("09961", "Trip.com"),
    ("09999", "NetEase"),
]


def _get(url: str) -> requests.Response:
    response = requests.get(
        url,
        headers={"User-Agent": "AbenFinancialDataCache/1.0"},
        timeout=60,
    )
    response.raise_for_status()
    return response


def sync_sp500() -> dict[str, Any]:
    html = _get(SP500_URL).text
    frame = pd.read_html(io.StringIO(html), attrs={"id": "constituents"})[0]
    stocks = []
    for _, row in frame.iterrows():
        raw_symbol = str(row["Symbol"]).strip()
        stocks.append(
            {
                "symbol": raw_symbol.replace(".", "-"),
                "source_symbol": raw_symbol,
                "name": str(row["Security"]).strip(),
                "exchange": "US",
                "currency": "USD",
                "market": "US",
                "sector": str(row["GICS Sector"]).strip(),
                "industry": str(row["GICS Sub-Industry"]).strip(),
                "cik": str(row["CIK"]).split(".")[0].zfill(10),
                "indexes": ["sp500"],
                "enabled": True,
            }
        )
    return {
        "id": "sp500",
        "name": "S&P 500",
        "source": SP500_URL,
        "constituent_count": len(stocks),
        "stocks": stocks,
    }


def sync_qqq() -> dict[str, Any]:
    html = _get(QQQ_URL).text
    frames = pd.read_html(io.StringIO(html))
    frame = next(
        table
        for table in frames
        if "Ticker" in table.columns and 95 <= len(table) <= 110
    )
    stocks = []
    for _, row in frame.iterrows():
        symbol = str(row["Ticker"]).strip().replace(".", "-")
        stocks.append(
            {
                "symbol": symbol,
                "source_symbol": str(row["Ticker"]).strip(),
                "name": str(row["Company"]).strip(),
                "exchange": "NASDAQ",
                "currency": "USD",
                "market": "US",
                "sector": str(row.get("ICB Industry[15]", "")).strip(),
                "industry": str(row.get("ICB Subsector[15]", "")).strip(),
                "indexes": ["qqq"],
                "enabled": True,
            }
        )
    return {
        "id": "qqq",
        "name": "Invesco QQQ / Nasdaq-100",
        "source": QQQ_URL,
        "source_note": "QQQ tracks the Nasdaq-100; share classes are separate securities.",
        "constituent_count": len(stocks),
        "stocks": stocks,
    }


def sync_csi300() -> dict[str, Any]:
    content = _get(CSI300_URL).content
    frame = pd.read_excel(io.BytesIO(content))
    stocks = []
    for _, row in frame.iterrows():
        code = str(int(row["成份券代码Constituent Code"])).zfill(6)
        exchange_name = str(row["交易所英文名称Exchange(Eng)"])
        suffix = ".SS" if "Shanghai" in exchange_name else ".SZ"
        stocks.append(
            {
                "symbol": f"{code}{suffix}",
                "source_symbol": code,
                "name": str(row["成份券英文名称Constituent Name(Eng)"]).strip(),
                "local_name": str(row["成份券名称Constituent Name"]).strip(),
                "exchange": "SSE" if suffix == ".SS" else "SZSE",
                "currency": "CNY",
                "market": "CN",
                "indexes": ["csi300"],
                "enabled": True,
            }
        )
    return {
        "id": "csi300",
        "name": "CSI 300",
        "source": CSI300_URL,
        "as_of": str(int(frame.iloc[0]["日期Date"])),
        "constituent_count": len(stocks),
        "stocks": stocks,
    }


def sync_hstech() -> dict[str, Any]:
    stocks = [
        {
            "symbol": f"{int(code):04d}.HK",
            "source_symbol": code,
            "name": name,
            "exchange": "HKEX",
            "currency": "HKD",
            "market": "HK",
            "indexes": ["hstech"],
            "enabled": True,
        }
        for code, name in HSTECH_CONSTITUENTS
    ]
    return {
        "id": "hstech",
        "name": "Hang Seng TECH Index",
        "source": "https://www.hsi.com.hk/eng/indexes/all-indexes/hstech",
        "as_of": "2025-06-09",
        "source_note": (
            "Curated public snapshot; verify against the latest quarterly "
            "Hang Seng Indexes review."
        ),
        "constituent_count": len(stocks),
        "stocks": stocks,
    }


def main() -> int:
    generated_at = datetime.now(timezone.utc).isoformat()
    indexes = [sync_sp500(), sync_qqq(), sync_csi300(), sync_hstech()]
    combined: dict[str, dict[str, Any]] = {}

    for index in indexes:
        index_payload = {
            "schema_version": 1,
            "generated_at": generated_at,
            **index,
        }
        write_json_atomic(
            INDEX_UNIVERSE_DIR / f"{index['id']}.json",
            index_payload,
        )
        for stock in index["stocks"]:
            symbol = stock["symbol"]
            if symbol in combined:
                combined[symbol]["indexes"] = sorted(
                    set(combined[symbol]["indexes"] + stock["indexes"])
                )
                for key, value in stock.items():
                    if key not in combined[symbol] or combined[symbol][key] in ("", None):
                        combined[symbol][key] = value
            else:
                combined[symbol] = stock

    payload = {
        "schema_version": 2,
        "generated_at": generated_at,
        "indexes": [
            {
                "id": index["id"],
                "name": index["name"],
                "constituent_count": index["constituent_count"],
            }
            for index in indexes
        ],
        "stocks": sorted(combined.values(), key=lambda stock: stock["symbol"]),
    }
    write_json_atomic(UNIVERSE_PATH, payload)
    print(
        f"Synced {len(indexes)} indexes and {len(combined)} unique securities."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
