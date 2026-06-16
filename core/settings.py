from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_PATH = REPO_ROOT / "universe" / "stocks.json"
INDEX_UNIVERSE_DIR = REPO_ROOT / "universe" / "indexes"
CACHE_ROOT = REPO_ROOT / "cache"
DCF_CACHE_DIR = CACHE_ROOT / "dcf"
MANIFEST_PATH = CACHE_ROOT / "manifest.json"

SOURCE_NAME = "yfinance"
SCHEMA_VERSION = 3
