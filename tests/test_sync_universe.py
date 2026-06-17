import unittest

from scripts.sync_universe import CSI_INDEXES, combine_index_stocks


class SyncUniverseTests(unittest.TestCase):
    def test_tracks_core_a_share_indexes(self) -> None:
        index_ids = {index_id for index_id, _, _ in CSI_INDEXES}

        self.assertTrue(
            {
                "sse50",
                "csi100",
                "csi200",
                "csi300",
                "csi500",
                "csi800",
                "csi1000",
                "csi2000",
                "csi_all",
                "star50",
                "star100",
            }.issubset(index_ids)
        )

    def test_combines_duplicate_symbols_and_merges_index_tags(self) -> None:
        stocks = combine_index_stocks(
            [
                {
                    "id": "csi300",
                    "stocks": [
                        {
                            "symbol": "688008.SS",
                            "name": "Montage Technology Co., Ltd.",
                            "exchange": "SSE",
                            "currency": "CNY",
                            "market": "CN",
                            "indexes": ["csi300"],
                            "enabled": True,
                        }
                    ],
                },
                {
                    "id": "star50",
                    "stocks": [
                        {
                            "symbol": "688008.SS",
                            "name": "",
                            "exchange": "SSE",
                            "currency": "CNY",
                            "market": "CN",
                            "indexes": ["star50"],
                            "enabled": True,
                        }
                    ],
                },
            ]
        )

        self.assertEqual(len(stocks), 1)
        self.assertEqual(stocks[0]["symbol"], "688008.SS")
        self.assertEqual(stocks[0]["name"], "Montage Technology Co., Ltd.")
        self.assertEqual(stocks[0]["indexes"], ["csi300", "star50"])


if __name__ == "__main__":
    unittest.main()
