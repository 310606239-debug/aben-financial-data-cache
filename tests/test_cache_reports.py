from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import rebuild_manifest
from scripts.report_cache_gaps import build_cache_gap_report


class CacheReportTests(unittest.TestCase):
    def write_universe(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "stocks": [
                        {
                            "symbol": "000001.SZ",
                            "name": "Ping An Bank",
                            "exchange": "SZSE",
                            "currency": "CNY",
                            "market": "CN",
                            "indexes": ["csi_all"],
                            "enabled": True,
                        },
                        {
                            "symbol": "000002.SZ",
                            "name": "Vanke",
                            "exchange": "SZSE",
                            "currency": "CNY",
                            "market": "CN",
                            "indexes": ["csi_all", "csi200"],
                            "enabled": True,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_rebuild_manifest_includes_current_failure_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache_dir = root / "dcf"
            failures_dir = root / "reports" / "failures"
            manifest_path = root / "manifest.json"
            cache_dir.mkdir(parents=True)
            failures_dir.mkdir(parents=True)

            (cache_dir / "000001.SZ.json").write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "symbol": "000001.SZ",
                        "fetched_at": "2026-06-17T00:00:00+00:00",
                        "market_data": {"as_of": "2026-06-17"},
                        "market": "CN",
                        "indexes": ["csi_all"],
                        "calculator_contract": {"forward_models": {"fcf_growth": {}}},
                    }
                ),
                encoding="utf-8",
            )
            (failures_dir / "update_cache_shard_0.json").write_text(
                json.dumps(
                    {
                        "source": "update_cache",
                        "shard_index": 0,
                        "shard_count": 1,
                        "failures": {"000002.SZ": "yfinance returned no current price"},
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(rebuild_manifest, "DCF_CACHE_DIR", cache_dir), mock.patch.object(
                rebuild_manifest, "CACHE_FAILURES_DIR", failures_dir
            ), mock.patch.object(rebuild_manifest, "MANIFEST_PATH", manifest_path):
                self.assertEqual(rebuild_manifest.main(), 0)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["stocks"]["000001.SZ"]["status"], "ok")
            self.assertEqual(manifest["stocks"]["000002.SZ"]["status"], "error")
            self.assertIn("yfinance returned", manifest["stocks"]["000002.SZ"]["error"])

    def test_gap_report_counts_missing_and_quality_issues(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache_dir = root / "dcf"
            cache_dir.mkdir()
            universe_path = root / "stocks.json"
            manifest_path = root / "manifest.json"
            self.write_universe(universe_path)

            (cache_dir / "000001.SZ.json").write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "symbol": "000001.SZ",
                        "market_data": {"price": 10, "shares_outstanding": None},
                        "annual": [{"fiscal_year": "2025-12-31"}],
                        "valuation_bases": {"free_cash_flow": {"per_share": 1}},
                    }
                ),
                encoding="utf-8",
            )
            manifest_path.write_text(
                json.dumps(
                    {
                        "stocks": {
                            "000001.SZ": {"status": "ok"},
                            "000002.SZ": {"status": "error", "error": "no data"},
                        }
                    }
                ),
                encoding="utf-8",
            )

            report = build_cache_gap_report(
                universe_path=universe_path,
                cache_dir=cache_dir,
                manifest_path=manifest_path,
                sample_limit=10,
            )

            self.assertEqual(report["summary"]["universe_count"], 2)
            self.assertEqual(report["summary"]["cached_count"], 1)
            self.assertEqual(report["summary"]["missing_count"], 1)
            self.assertEqual(report["summary"]["error_count"], 1)
            self.assertEqual(report["quality_counts"]["missing_shares"], 1)
            self.assertEqual(report["quality_counts"]["short_annual_history"], 1)
            self.assertEqual(report["by_index"]["csi200"]["missing"], 1)


if __name__ == "__main__":
    unittest.main()
