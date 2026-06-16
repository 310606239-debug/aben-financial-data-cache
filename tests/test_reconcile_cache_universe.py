from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.reconcile_cache_universe import reconcile_cache_metadata


class ReconcileCacheUniverseTests(unittest.TestCase):
    def test_updates_existing_cache_indexes_from_universe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            cache_dir = root / "cache"
            cache_dir.mkdir()
            universe_path = root / "stocks.json"

            universe_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "stocks": [
                            {
                                "symbol": "688008.SS",
                                "name": "Montage Technology Co., Ltd.",
                                "exchange": "SSE",
                                "currency": "CNY",
                                "market": "CN",
                                "indexes": ["csi300", "star50"],
                                "enabled": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            cache_path = cache_dir / "688008.SS.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "symbol": "688008.SS",
                        "name": "Old Name",
                        "exchange": "SSE",
                        "currency": "CNY",
                        "market": "CN",
                        "indexes": ["csi300"],
                    }
                ),
                encoding="utf-8",
            )

            changed = reconcile_cache_metadata(cache_dir, universe_path)

            self.assertEqual(changed, 1)
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["name"], "Montage Technology Co., Ltd.")
            self.assertEqual(payload["indexes"], ["csi300", "star50"])


if __name__ == "__main__":
    unittest.main()
