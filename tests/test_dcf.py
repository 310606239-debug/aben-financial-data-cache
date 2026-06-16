import unittest

from core.dcf import forward_fair_value, reverse_implied_growth


class DcfTests(unittest.TestCase):
    def test_forward_and_reverse_are_inverse(self) -> None:
        fair_value = forward_fair_value(
            base_per_share=10,
            growth_rate=0.12,
            projection_years=10,
            discount_rate=0.10,
            terminal_multiple=20,
        )
        implied_growth = reverse_implied_growth(
            current_price=fair_value,
            base_per_share=10,
            projection_years=10,
            discount_rate=0.10,
            terminal_multiple=20,
        )

        self.assertAlmostEqual(implied_growth, 0.12)

    def test_revenue_model_applies_margin(self) -> None:
        fair_value = forward_fair_value(
            base_per_share=100,
            growth_rate=0,
            projection_years=5,
            discount_rate=0,
            terminal_multiple=20,
            margin=0.25,
        )

        self.assertEqual(fair_value, 500)


if __name__ == "__main__":
    unittest.main()
