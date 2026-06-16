import unittest

from core.yfinance_client import _merge_existing_annual


class YFinanceClientTests(unittest.TestCase):
    def test_merge_existing_annual_preserves_old_years_and_values(self) -> None:
        existing = [
            {
                "fiscal_year": "2024-12-31",
                "source": "sec-edgar",
                "revenue": 100,
                "year_end_price": 50,
            },
            {
                "fiscal_year": "2014-12-31",
                "source": "sec-edgar",
                "revenue": 10,
            },
        ]
        refreshed = [
            {
                "fiscal_year": "2025-12-31",
                "source": "yfinance",
                "revenue": 120,
            },
            {
                "fiscal_year": "2024-12-31",
                "source": "yfinance",
                "revenue": None,
                "year_end_price": None,
            },
        ]

        annual = _merge_existing_annual(existing, refreshed)

        self.assertEqual([row["fiscal_year"][:4] for row in annual], ["2025", "2024", "2014"])
        self.assertEqual(annual[1]["revenue"], 100)
        self.assertEqual(annual[1]["year_end_price"], 50)

    def test_merge_existing_annual_does_not_trim_long_history(self) -> None:
        existing = [
            {"fiscal_year": f"{year}-12-31", "revenue": year}
            for year in range(2010, 2025)
        ]
        refreshed = [{"fiscal_year": "2025-12-31", "revenue": 2025}]

        annual = _merge_existing_annual(existing, refreshed)

        self.assertEqual(len(annual), 16)
        self.assertEqual(annual[0]["fiscal_year"], "2025-12-31")
        self.assertEqual(annual[-1]["fiscal_year"], "2010-12-31")


if __name__ == "__main__":
    unittest.main()
