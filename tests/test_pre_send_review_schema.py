import tempfile
import unittest
from pathlib import Path

from zyw_insight.email_draft import build_email_draft
from zyw_insight.pipeline import run_72h_dry_run_pipeline
from zyw_insight.pre_send_review import run_pre_send_review
from zyw_insight.schema_validation import validate_json


class PreSendReviewSchemaTests(unittest.TestCase):
    def test_pre_send_review_schema_valid(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = run_72h_dry_run_pipeline("examples/sample_inputs", output_dir=root / "run")
            draft = build_email_draft(run["artifacts"]["output_dir"], output_dir=root / "draft")
            review = run_pre_send_review(Path(draft["body"]["markdown_path"]).parent, output_dir=root / "review")
            self.assertTrue(validate_json(review, "pre_send_review"))
            self.assertTrue(review["dry_run"])
            self.assertIn(review["overall_decision"], {"ready_for_human_review", "needs_revision", "blocked"})
            self.assertNotEqual(review["overall_decision"], "approved_for_send")
            self.assertFalse(review["runtime_boundary"]["model_called"])
            self.assertFalse(review["runtime_boundary"]["email_sent"])


if __name__ == "__main__":
    unittest.main()
