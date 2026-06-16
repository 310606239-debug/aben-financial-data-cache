import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from core import update_policy
from core.universe import Stock
from core.update_policy import UpdatePolicy, parse_datetime, select_refresh_candidates


class UpdatePolicyTests(unittest.TestCase):
    def stock(self, symbol: str = "AAPL") -> Stock:
        return Stock(
            symbol=symbol,
            name=symbol,
            exchange="NASDAQ",
            currency="USD",
            market="US",
            indexes=("sp500",),
        )

    def test_parse_datetime_accepts_z_suffix(self) -> None:
        parsed = parse_datetime("2026-06-16T12:00:00Z")

        self.assertEqual(parsed, datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc))

    def test_missing_cache_is_selected(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            update_policy, "DCF_CACHE_DIR", Path(directory)
        ):
            selected = select_refresh_candidates(
                [self.stock()],
                UpdatePolicy(stale_days=7),
                {},
            )

        self.assertEqual([stock.symbol for stock in selected], ["AAPL"])

    def test_fresh_cache_is_skipped_when_stale_days_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            update_policy, "DCF_CACHE_DIR", Path(directory)
        ):
            (Path(directory) / "AAPL.json").write_text("{}", encoding="utf-8")
            selected = select_refresh_candidates(
                [self.stock()],
                UpdatePolicy(stale_days=7),
                {"AAPL": {"status": "ok", "fetched_at": "2026-06-15T12:00:00+00:00"}},
            )

        self.assertEqual(selected, [])

    def test_error_cache_is_retried_even_when_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            update_policy, "DCF_CACHE_DIR", Path(directory)
        ):
            (Path(directory) / "AAPL.json").write_text("{}", encoding="utf-8")
            selected = select_refresh_candidates(
                [self.stock()],
                UpdatePolicy(stale_days=7),
                {"AAPL": {"status": "error", "fetched_at": "2026-06-16T12:00:00+00:00"}},
            )

        self.assertEqual([stock.symbol for stock in selected], ["AAPL"])


if __name__ == "__main__":
    unittest.main()
