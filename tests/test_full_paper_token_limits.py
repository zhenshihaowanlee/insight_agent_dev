import unittest

from zyw_insight.token_budget import calibrate_token_estimate, estimate_tokens_rough, select_fulltext_under_token_cap, validate_one_shot_token_budget


class FullPaperTokenLimitTests(unittest.TestCase):
    def test_estimate_and_selection_above_min_for_large_text(self):
        text = "MegaScale-Infer GPU communication datacenter systems p99 evaluation. " * 1400
        selection = select_fulltext_under_token_cap(text, 18000, 28000, "openrouter/qwen/qwen3.5-397b-a17b")
        self.assertGreaterEqual(selection["conservative_estimated_input_tokens"], 8000)
        self.assertLessEqual(selection["conservative_estimated_input_tokens"], 28000)
        self.assertTrue(selection["expected_actual_input_safe"])

    def test_conservative_factor_for_qwen_is_at_least_2_2(self):
        rough = estimate_tokens_rough("x" * 60000)
        conservative = calibrate_token_estimate(rough, "openrouter/qwen/qwen3.5-397b-a17b")
        self.assertGreater(conservative, rough)
        self.assertGreaterEqual(conservative, int(rough * 2.2))

    def test_selection_truncates_when_full_text_exceeds_cap(self):
        text = "Abstract method architecture implementation evaluation baseline limitations conclusion. " * 1500
        selection = select_fulltext_under_token_cap(text, 18000, 28000, "openrouter/qwen/qwen3.5-397b-a17b")
        self.assertLess(selection["included_char_count"], len(text))
        self.assertLessEqual(selection["conservative_estimated_input_tokens"], 28000)

    def test_budget_validation_rejects_total_over_cap(self):
        result = validate_one_shot_token_budget(35000, 8000, 40000)
        self.assertFalse(result["ok"])
        self.assertIn("max_total_tokens_hard", " ".join(result["errors"]))


if __name__ == "__main__":
    unittest.main()
