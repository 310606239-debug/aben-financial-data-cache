from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.universe import Stock
from scripts.validate_cache import validate_cache_entries


class ValidateCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stock = Stock(
            symbol="VYLR",
            name="Vaylar",
            exchange="NASDAQ",
            currency="USD",
            market="US",
            indexes=("sp500",),
        )

    def test_incomplete_cache_reduces_valid_coverage_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            cache_dir = Path(temporary_dir)
            (cache_dir / "VYLR.json").write_text(
                json.dumps(
                    {
                        "symbol": "VYLR",
                        "market_data": {"price": 10, "shares_outstanding": None},
                        "annual": [{"fiscal_year": "2025"}],
                        "valuation_bases": {"earnings": {"per_share": 1}},
                    }
                ),
                encoding="utf-8",
            )

            valid, missing, issues = validate_cache_entries(
                [self.stock],
                {"stocks": {"VYLR": {"status": "ok"}}},
                cache_dir,
                allow_missing_price=True,
            )

            self.assertEqual(valid, 0)
            self.assertEqual(missing, 0)
            self.assertEqual(issues, {"VYLR": ["missing shares outstanding"]})

    def test_valid_cache_counts_toward_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            cache_dir = Path(temporary_dir)
            (cache_dir / "VYLR.json").write_text(
                json.dumps(
                    {
                        "symbol": "VYLR",
                        "market_data": {"price": 10, "shares_outstanding": 100},
                        "annual": [{"fiscal_year": "2025"}],
                        "valuation_bases": {"earnings": {"per_share": 1}},
                    }
                ),
                encoding="utf-8",
            )

            valid, missing, issues = validate_cache_entries(
                [self.stock],
                {"stocks": {"VYLR": {"status": "ok"}}},
                cache_dir,
                allow_missing_price=False,
            )

            self.assertEqual((valid, missing, issues), (1, 0, {}))


if __name__ == "__main__":
    unittest.main()
