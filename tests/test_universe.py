import json
import tempfile
import unittest
from pathlib import Path

from core.universe import load_universe


class LoadUniverseTests(unittest.TestCase):
    def write_payload(self, payload: dict) -> Path:
        temporary = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False
        )
        with temporary:
            json.dump(payload, temporary)
        self.addCleanup(Path(temporary.name).unlink, missing_ok=True)
        return Path(temporary.name)

    def test_loads_enabled_stocks_and_normalizes_symbol(self) -> None:
        path = self.write_payload(
            {
                "schema_version": 1,
                "stocks": [
                    {
                        "symbol": " tsla ",
                        "name": "Tesla",
                        "exchange": "NASDAQ",
                        "currency": "USD",
                        "enabled": True,
                    },
                    {"symbol": "OFF", "enabled": False},
                ],
            }
        )

        stocks = load_universe(path)

        self.assertEqual([stock.symbol for stock in stocks], ["TSLA"])

    def test_rejects_duplicate_symbols(self) -> None:
        path = self.write_payload(
            {
                "schema_version": 1,
                "stocks": [{"symbol": "TSLA"}, {"symbol": "tsla"}],
            }
        )

        with self.assertRaisesRegex(ValueError, "Duplicate symbol"):
            load_universe(path)


if __name__ == "__main__":
    unittest.main()
