from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_PATH = REPO_ROOT / "universe" / "stocks.json"
INDEX_UNIVERSE_DIR = REPO_ROOT / "universe" / "indexes"
CACHE_ROOT = REPO_ROOT / "cache"
DCF_CACHE_DIR = CACHE_ROOT / "dcf"
DCF_HISTORY_DIR = CACHE_ROOT / "history" / "dcf"
PRICE_HISTORY_DIR = CACHE_ROOT / "history" / "prices"
CACHE_REPORTS_DIR = CACHE_ROOT / "reports"
CACHE_FAILURES_DIR = CACHE_REPORTS_DIR / "failures"
PREVIOUS_DCF_CACHE_DIR = CACHE_ROOT / "_previous_dcf"
MANIFEST_PATH = CACHE_ROOT / "manifest.json"

SOURCE_NAME = "yfinance"
SCHEMA_VERSION = 3
