from __future__ import annotations

import io
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from core.cache import write_json_atomic
from core.settings import INDEX_UNIVERSE_DIR, UNIVERSE_PATH


SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
QQQ_URL = "https://en.wikipedia.org/wiki/Nasdaq-100"
CSI_AUTOFILE_BASE_URL = (
    "https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/"
    "file/autofile/cons/{code}cons.xls"
)
DOWNLOAD_ATTEMPTS = int(os.getenv("ABEN_UNIVERSE_DOWNLOAD_ATTEMPTS", "2"))
DOWNLOAD_TIMEOUT = int(os.getenv("ABEN_UNIVERSE_DOWNLOAD_TIMEOUT", "60"))

CSI_INDEXES = [
    ("sse50", "SSE 50", "000016"),
    ("csi100", "CSI 100", "000903"),
    ("csi200", "CSI 200", "000904"),
    ("csi300", "CSI 300", "000300"),
    ("csi500", "CSI 500", "000905"),
    ("csi800", "CSI 800", "000906"),
    ("csi1000", "CSI 1000", "000852"),
    ("csi2000", "CSI 2000", "932000"),
    ("csi_all", "CSI All Share", "000985"),
    ("star50", "SSE STAR 50", "000688"),
    ("star100", "SSE STAR 100", "000698"),
]

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

CHINEXT_CONSTITUENTS = [
    ("300308", "中际旭创", "电信业务"),
    ("300750", "宁德时代", "工业"),
    ("300502", "新易盛", "电信业务"),
    ("300059", "东方财富", "金融"),
    ("300274", "阳光电源", "工业"),
    ("300476", "胜宏科技", "信息技术"),
    ("300394", "天孚通信", "电信业务"),
    ("300408", "三环集团", "信息技术"),
    ("300124", "汇川技术", "工业"),
    ("301308", "江波龙", "信息技术"),
    ("300604", "长川科技", "信息技术"),
    ("300014", "亿纬锂能", "工业"),
    ("300433", "蓝思科技", "信息技术"),
    ("300760", "迈瑞医疗", "医药卫生"),
    ("300136", "信维通信", "电信业务"),
    ("300857", "协创数据", "信息技术"),
    ("300498", "温氏股份", "主要消费"),
    ("300475", "香农芯创", "信息技术"),
    ("300757", "罗博特科", "信息技术"),
    ("300548", "长芯博创", "电信业务"),
    ("300033", "同花顺", "信息技术"),
    ("300666", "江丰电子", "信息技术"),
    ("300054", "鼎龙股份", "信息技术"),
    ("300223", "北京君正", "信息技术"),
    ("300285", "国瓷材料", "原材料"),
    ("300395", "菲利华", "原材料"),
    ("300442", "润泽科技", "信息技术"),
    ("300058", "蓝色光标", "可选消费"),
    ("300450", "先导智能", "工业"),
    ("300390", "天华新能", "工业"),
    ("300661", "圣邦股份", "信息技术"),
    ("300620", "光库科技", "电信业务"),
    ("300672", "国科微", "信息技术"),
    ("301526", "国际复材", "原材料"),
    ("301217", "铜冠铜箔", "信息技术"),
    ("300567", "精测电子", "信息技术"),
    ("300037", "新宙邦", "工业"),
    ("300346", "南大光电", "信息技术"),
    ("300015", "爱尔眼科", "医药卫生"),
    ("301377", "鼎泰高科", "工业"),
    ("300803", "指南针", "信息技术"),
    ("300751", "迈为股份", "工业"),
    ("300418", "昆仑万维", "信息技术"),
    ("300782", "卓胜微", "信息技术"),
    ("301358", "湖南裕能", "工业"),
    ("300017", "网宿科技", "信息技术"),
    ("300316", "晶盛机电", "工业"),
    ("300373", "扬杰科技", "信息技术"),
    ("300339", "润和软件", "信息技术"),
    ("300115", "长盈精密", "信息技术"),
    ("300207", "欣旺达", "信息技术"),
    ("300001", "特锐德", "工业"),
    ("301236", "软通动力", "信息技术"),
    ("300866", "安克创新", "信息技术"),
    ("300432", "富临精工", "可选消费"),
    ("300454", "深信服", "信息技术"),
    ("300458", "全志科技", "信息技术"),
    ("300748", "金力永磁", "原材料"),
    ("301200", "大族数控", "工业"),
    ("300024", "机器人", "工业"),
    ("300496", "中科创达", "信息技术"),
    ("300759", "康龙化成", "医药卫生"),
    ("300073", "当升科技", "工业"),
    ("300919", "中伟新材", "工业"),
    ("300347", "泰格医药", "医药卫生"),
    ("300763", "锦浪科技", "工业"),
    ("301269", "华大九天", "信息技术"),
    ("300724", "捷佳伟创", "工业"),
    ("300012", "华测检测", "工业"),
    ("301536", "星宸科技", "信息技术"),
    ("300255", "常山药业", "医药卫生"),
    ("300953", "震裕科技", "工业"),
    ("300474", "景嘉微", "信息技术"),
    ("300383", "光环新网", "信息技术"),
    ("300677", "英科医疗", "医药卫生"),
    ("300972", "万辰集团", "主要消费"),
    ("302132", "中航成飞", "工业"),
    ("301611", "珂玛科技", "信息技术"),
    ("300251", "光线传媒", "可选消费"),
    ("300628", "亿联网络", "电信业务"),
    ("300699", "光威复材", "原材料"),
    ("300832", "新产业", "医药卫生"),
    ("301550", "斯菱智驱", "可选消费"),
    ("300627", "华测导航", "电信业务"),
    ("300487", "蓝晓科技", "原材料"),
    ("300002", "神州泰岳", "信息技术"),
    ("300999", "金龙鱼", "主要消费"),
    ("300122", "智飞生物", "医药卫生"),
    ("300003", "乐普医疗", "医药卫生"),
    ("300253", "卫宁健康", "信息技术"),
    ("300896", "爱美客", "医药卫生"),
    ("300144", "宋城演艺", "可选消费"),
    ("300413", "芒果超媒", "可选消费"),
    ("300718", "长盛轴承", "工业"),
    ("301165", "锐捷网络", "电信业务"),
    ("300765", "新诺威", "主要消费"),
    ("300979", "华利集团", "可选消费"),
    ("301301", "川宁生物", "医药卫生"),
    ("300888", "稳健医疗", "可选消费"),
    ("301498", "乖宝宠物", "主要消费"),
]


def _get(url: str) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "AbenFinancialDataCache/1.0"},
                timeout=DOWNLOAD_TIMEOUT,
            )
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            last_error = error
            if attempt == DOWNLOAD_ATTEMPTS:
                break
            print(f"Retrying {url} after download error: {error}")
            time.sleep(attempt * 5)
    raise last_error or RuntimeError(f"Failed to download {url}")


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


def sync_csi_excel(index_id: str, name: str, url: str) -> dict[str, Any]:
    content = _get(url).content
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
                "indexes": [index_id],
                "enabled": True,
            }
        )
    return {
        "id": index_id,
        "name": name,
        "source": url,
        "as_of": str(int(frame.iloc[0]["日期Date"])),
        "constituent_count": len(stocks),
        "stocks": stocks,
    }


def sync_csi_configured_index(index_id: str, name: str, code: str) -> dict[str, Any]:
    print(f"Syncing {index_id} ({code}) from CSI official constituent file.")
    return sync_csi_excel(index_id, name, CSI_AUTOFILE_BASE_URL.format(code=code))


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


def sync_chinext() -> dict[str, Any]:
    stocks = [
        {
            "symbol": f"{code}.SZ",
            "source_symbol": code,
            "name": local_name,
            "local_name": local_name,
            "exchange": "SZSE",
            "currency": "CNY",
            "market": "CN",
            "sector": sector,
            "indexes": ["chinext"],
            "enabled": True,
        }
        for code, local_name, sector in CHINEXT_CONSTITUENTS
    ]
    return {
        "id": "chinext",
        "name": "ChiNext Index",
        "source": (
            "https://www.cnindex.com.cn/module/"
            "index-detail.html?act_menu=1&indexCode=399006"
        ),
        "as_of": "2026-06-16",
        "source_note": (
            "CNI Index current constituents snapshot downloaded from "
            "399006_cons_2026-06-16.xls; replace with live download once "
            "the official endpoint is stable in CI."
        ),
        "constituent_count": len(stocks),
        "stocks": stocks,
    }


def sync_or_load_existing(index_id: str, sync_fn) -> dict[str, Any]:
    try:
        return sync_fn()
    except Exception:
        path = INDEX_UNIVERSE_DIR / f"{index_id}.json"
        if not path.exists():
            raise
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
        return {
            key: value
            for key, value in payload.items()
            if key not in {"schema_version", "generated_at"}
        }


def combine_index_stocks(indexes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}

    for index in indexes:
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

    return sorted(combined.values(), key=lambda stock: stock["symbol"])


def main() -> int:
    generated_at = datetime.now(timezone.utc).isoformat()
    indexes = [
        sync_or_load_existing("sp500", sync_sp500),
        sync_or_load_existing("qqq", sync_qqq),
        *[
            sync_or_load_existing(
                index_id,
                lambda index_id=index_id, name=name, code=code: sync_csi_configured_index(
                    index_id, name, code
                ),
            )
            for index_id, name, code in CSI_INDEXES
        ],
        sync_chinext(),
        sync_hstech(),
    ]

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

    stocks = combine_index_stocks(indexes)

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
        "stocks": stocks,
    }
    write_json_atomic(UNIVERSE_PATH, payload)
    print(
        f"Synced {len(indexes)} indexes and {len(stocks)} unique securities."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
