import tempfile
import unittest
from pathlib import Path

from zyw_insight.email_draft import build_email_draft
from zyw_insight.pipeline import run_72h_dry_run_pipeline
from zyw_insight.pre_send_review import run_pre_send_review


class PreSendReviewTests(unittest.TestCase):
    def _review(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        run = run_72h_dry_run_pipeline("examples/sample_inputs", output_dir=root / "run")
        draft = build_email_draft(run["artifacts"]["output_dir"], output_dir=root / "draft")
        return run_pre_send_review(Path(draft["body"]["markdown_path"]).parent, output_dir=root / "review")

    def test_role_reviews_present(self):
        review = self._review()
        roles = {item["role"] for item in review["reviewer_panel"]}
        self.assertEqual(
            roles,
            {"evidence_skeptic", "constraint_integrity", "delivery_safety", "executive_readability", "budget_runtime_boundary"},
        )

    def test_evidence_and_constraint_checks(self):
        review = self._review()
        self.assertIn("evidence_skeptic_review", review)
        self.assertIn("constraint_review", review)
        constraint_messages = " ".join(finding["message"] for finding in review["constraint_review"]["findings"])
        self.assertNotIn("Network Metric Trends missing dimensions", constraint_messages)

    def test_delivery_and_readability_checks(self):
        review = self._review()
        self.assertIn("delivery_safety_review", review)
        self.assertIn("executive_readability_review", review)
        readability = " ".join(finding["message"] for finding in review["executive_readability_review"]["findings"])
        self.assertNotIn("debug/placeholder", readability)

    def test_review_artifacts_and_redaction(self):
        review = self._review()
        json_path = Path(review["artifacts"]["json_path"])
        md_path = Path(review["artifacts"]["markdown_path"])
        self.assertTrue(json_path.exists())
        self.assertTrue(md_path.exists())
        combined = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
        for marker in ("OPENROUTER_API_KEY", "Authorization", "Bearer", "sk-", "token", "secret", "smtp", "sendmail", "webhook"):
            self.assertNotIn(marker, combined)

    def test_budget_runtime_boundary(self):
        review = self._review()
        boundary = review["budget_runtime_boundary_review"]
        self.assertIn(boundary["severity"], {"info", "warning"})
        self.assertFalse(review["runtime_boundary"]["codex_runtime_used"])
        self.assertFalse(review["runtime_boundary"]["real_openrouter_call_executed"])

    def test_negative_guardrail_does_not_force_needs_revision(self):
        review = self._review()
        self.assertEqual(review["overall_decision"], "ready_for_human_review")

    def test_true_strong_claim_fixture_is_detected(self):
        review = self._review()
        draft_dir = Path(review["source_email_draft_manifest"]).parent
        brief_path = Path(review["source_brief_markdown"])
        original = brief_path.read_text(encoding="utf-8")
        try:
            brief_path.write_text(original + "\nready for production\n", encoding="utf-8")
            from zyw_insight.pre_send_review import run_pre_send_review

            revised = run_pre_send_review(draft_dir, output_dir=draft_dir / "strong-review")
            self.assertEqual(revised["overall_decision"], "needs_revision")
            self.assertNotEqual(revised["overall_decision"], "approved_for_send")
        finally:
            brief_path.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
