import unittest

from zyw_insight.openrouter_canary import _annotate_cost_audit, _annotate_usage_estimate, build_canary_payload, execute_openrouter_canary
from zyw_insight.budget import resolve_audit_cost


class CanaryCostUsageTests(unittest.TestCase):
    def test_default_canary_max_tokens_is_256(self):
        payload = build_canary_payload("literature_analysis", {"source_id": "s1"}, "openrouter/example/model")
        self.assertEqual(payload["max_tokens"], 256)

    def test_dry_run_estimated_output_tokens_tracks_canary_max_tokens(self):
        run = execute_openrouter_canary("literature_analysis", {"source_id": "s1"}, "openrouter/example/model")
        self.assertEqual(run["request"]["payload"]["max_tokens"], 256)
        self.assertGreaterEqual(run["usage"]["estimated_output_tokens"], 256)

    def test_under_prediction_flag_and_ratio(self):
        usage = {"estimated_output_tokens": 256, "actual_output_tokens": 1200}
        _annotate_usage_estimate(usage)
        self.assertTrue(usage["estimate_under_predicted"])
        self.assertEqual(usage["estimate_error_ratio"], 4.6875)

    def test_cost_fallback_uses_estimated_when_actual_missing(self):
        cost = {"estimated_cost_usd": 0.01, "actual_cost_usd": None}
        _annotate_cost_audit(cost)
        self.assertEqual(cost["actual_cost_source"], "estimated_fallback")
        self.assertEqual(cost["audit_cost_usd"], 0.01)
        self.assertEqual(resolve_audit_cost(None, 0.01)["audit_cost_usd"], 0.01)

    def test_cost_uses_actual_when_present(self):
        cost = {"estimated_cost_usd": 0.01, "actual_cost_usd": 0.02}
        _annotate_cost_audit(cost)
        self.assertEqual(cost["actual_cost_source"], "openrouter_usage")
        self.assertEqual(cost["audit_cost_usd"], 0.02)


if __name__ == "__main__":
    unittest.main()
