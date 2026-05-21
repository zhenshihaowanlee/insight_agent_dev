import json
import unittest
from pathlib import Path

from zyw_insight.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "redacted_real_canary_minimal.json"


class RealCanaryRegressionTests(unittest.TestCase):
    def test_redacted_real_canary_fixture_schema_valid(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertTrue(validate_json(payload, "openrouter_canary"))

    def test_fixture_contains_no_raw_model_or_secret_material(self):
        raw = FIXTURE.read_text(encoding="utf-8")
        forbidden = [
            "Thinking Process",
            "reasoning_details\": [",
            "content\":",
            "messages\":",
            "body\":",
            "OPENROUTER_API_KEY",
            "Authorization",
            "Bearer",
            "sk-",
            "secret",
        ]
        for marker in forbidden:
            self.assertNotIn(marker, raw)

    def test_fixture_records_usage_cost_and_boolean_manual_required(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertIs(payload["ledger_event"]["manual_required"], False)
        self.assertTrue(payload["usage"]["estimate_under_predicted"])
        self.assertGreater(payload["usage"]["actual_output_tokens"], payload["usage"]["estimated_output_tokens"])
        self.assertEqual(payload["cost"]["actual_cost_source"], "openrouter_usage")


if __name__ == "__main__":
    unittest.main()
