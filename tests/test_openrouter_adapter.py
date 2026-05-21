import unittest
from pathlib import Path

from zyw_insight.ingestion import ingest_file
from zyw_insight.openrouter_adapter import build_model_request, dry_run_model_request, run_adapter_dry_run
from zyw_insight.budget import load_budget_policy
from zyw_insight.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]


class OpenRouterAdapterTests(unittest.TestCase):
    def test_build_model_request_schema_valid(self):
        policy = load_budget_policy("quality_first")
        payload = ingest_file(ROOT / "examples/sample_inputs/sample_paper.md")
        request = build_model_request(
            "literature_analysis",
            payload,
            policy,
            spent_usd=50,
            triage_result={"source_tier": "A", "deep_read_priority": "High"},
        )
        self.assertTrue(validate_json(request, "model_request"))
        self.assertEqual(request["provider"], "openrouter")
        self.assertTrue(request["model_id"].startswith("openrouter/"))
        self.assertIs(request["dry_run"], True)

    def test_dry_run_response_boundary(self):
        run = run_adapter_dry_run(
            "literature_analysis",
            ingest_file(ROOT / "examples/sample_inputs/sample_paper.md"),
            spent_usd=50,
            triage_result={"source_tier": "A", "deep_read_priority": "High"},
        )
        self.assertTrue(validate_json(run["response"], "model_response"))
        self.assertTrue(run["runtime_boundary"]["openrouter_only"])
        self.assertFalse(run["runtime_boundary"]["codex_runtime_used"])
        self.assertFalse(run["runtime_boundary"]["network_request_sent"])
        self.assertEqual(run["response"]["status"], "mock_success")

    def test_final_review_manual_only_without_override(self):
        run = run_adapter_dry_run("final_review", {"brief_id": "b1"}, spent_usd=50)
        self.assertTrue(run["response"]["manual_required"])
        self.assertFalse(run["response"]["processing_allowed"])
        self.assertIn(run["response"]["status"], {"skipped", "denied"})
        self.assertNotEqual(run["response"]["model_id"], "openrouter/premium-final-review-placeholder")

    def test_manual_override_changes_final_review_dry_run_status(self):
        run = run_adapter_dry_run("final_review", {"brief_id": "b1"}, spent_usd=50, manual_override=True)
        self.assertTrue(run["response"]["manual_required"])
        self.assertTrue(run["response"]["processing_allowed"])
        self.assertTrue(run["dry_run"])

    def test_quality_first_high_priority_preserves_model(self):
        run = run_adapter_dry_run(
            "literature_analysis",
            ingest_file(ROOT / "examples/sample_inputs/sample_paper.md"),
            spent_usd=410,
            triage_result={"source_tier": "A", "deep_read_priority": "High"},
        )
        self.assertEqual(run["request"]["model_id"], "openrouter/long-context-analysis-placeholder")
        self.assertTrue(run["request"]["routing_decision"]["quality_preserved"])

    def test_quality_first_low_priority_denied(self):
        run = run_adapter_dry_run(
            "literature_analysis",
            ingest_file(ROOT / "examples/sample_inputs/vendor_whitepaper.txt"),
            spent_usd=410,
            triage_result={"source_tier": "D", "deep_read_priority": "Low"},
        )
        self.assertFalse(run["response"]["processing_allowed"])
        self.assertEqual(run["response"]["status"], "denied")

    def test_hard_cap_denied(self):
        run = run_adapter_dry_run("literature_analysis", {"source_id": "x"}, spent_usd=600)
        self.assertFalse(run["response"]["processing_allowed"])


if __name__ == "__main__":
    unittest.main()
