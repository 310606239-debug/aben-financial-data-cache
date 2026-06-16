import unittest

from core.metrics import available_windows, historical_average


class MetricsTests(unittest.TestCase):
    def test_windows_require_enough_periods(self) -> None:
        annual = [{"revenue": value} for value in range(6)]

        self.assertEqual(available_windows(annual, "revenue"), [1, 3, 5])

    def test_average_is_null_when_full_window_is_unavailable(self) -> None:
        annual = [{"margin": 0.2}, {"margin": 0.3}]

        averages = historical_average(annual, "margin")

        self.assertEqual(averages["1y"], 0.2)
        self.assertIsNone(averages["3y"])


if __name__ == "__main__":
    unittest.main()
