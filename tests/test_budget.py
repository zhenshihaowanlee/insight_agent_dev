import unittest

from zyw_insight.budget import budget_mode, estimate_scenario


class BudgetTests(unittest.TestCase):
    def test_baseline_efficient_nano_cost(self):
        cost = estimate_scenario("gpt-5.4-nano", "baseline_efficient")
        self.assertGreater(cost, 0)
        self.assertLess(cost, 30)

    def test_budget_modes(self):
        self.assertEqual(budget_mode(0), "normal")
        self.assertEqual(budget_mode(220, soft_limit_usd=300), "reduce_reasoning_and_critic_scope")
        self.assertEqual(budget_mode(280, soft_limit_usd=300), "restrict_to_a_rank_and_manual")
        self.assertEqual(budget_mode(320, soft_limit_usd=300, hard_limit_usd=400), "high_restriction")
        self.assertEqual(budget_mode(410, soft_limit_usd=300, hard_limit_usd=400), "stop_auto_deep_analysis")


if __name__ == "__main__":
    unittest.main()
