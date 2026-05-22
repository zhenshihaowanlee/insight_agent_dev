import unittest

from zyw_insight.score_consistency import compare_score_action, compute_weighted_score, map_score_to_action, validate_score_consistency


class ScoreConsistencyTests(unittest.TestCase):
    def test_compute_weighted_score_sums_component_scores(self):
        score = {"a": {"score": 10, "weight": 20}, "b": {"score": 12.5, "weight": 30}, "total_score": 80}
        self.assertEqual(compute_weighted_score(score), 22.5)

    def test_total_mismatch_detected(self):
        result = validate_score_consistency({"a": {"score": 10, "weight": 20}, "total_score": 82})
        self.assertTrue(result["score_total_mismatch"])

    def test_score_action_mismatch_detected(self):
        result = compare_score_action(82, "C")
        self.assertTrue(result["score_action_mismatch"])
        self.assertEqual(result["score_suggested_action"], "A")
        self.assertTrue(result["downgrade_reason_required"])

    def test_score_to_action_bands(self):
        self.assertEqual(map_score_to_action(86), "A")
        self.assertEqual(map_score_to_action(72), "A")
        self.assertEqual(map_score_to_action(60), "B")
        self.assertEqual(map_score_to_action(45), "C")
        self.assertEqual(map_score_to_action(20), "D")


if __name__ == "__main__":
    unittest.main()
