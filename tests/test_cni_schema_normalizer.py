import unittest

from zyw_insight.cni_schema_normalizer import normalize_score_fields, validate_normalized_literature_analysis


class CNISchemaNormalizerTests(unittest.TestCase):
    def test_score_string_normalizes(self):
        data = normalize_score_fields({"score": {"total_score": "72"}})
        self.assertEqual(data["score"]["total_score"], 72.0)

    def test_score_ratio_normalizes(self):
        data = normalize_score_fields({"score": {"total_score": "72/100"}})
        self.assertEqual(data["score"]["total_score"], 72.0)

    def test_score_high_does_not_normalize(self):
        data = normalize_score_fields({"score": {"total_score": "high"}})
        self.assertEqual(data["score"]["total_score"], "high")

    def test_score_null_does_not_normalize(self):
        data = normalize_score_fields({"score": {"total_score": None}})
        self.assertIsNone(data["score"]["total_score"])

    def test_missing_total_score_fails_validation(self):
        result = validate_normalized_literature_analysis({"score": {}})
        self.assertFalse(result["schema_valid"])


if __name__ == "__main__":
    unittest.main()
