import tempfile
import unittest
from pathlib import Path

from zyw_insight.email_draft import build_email_draft
from zyw_insight.pipeline import run_72h_dry_run_pipeline
from zyw_insight.schema_validation import validate_json


class EmailDraftSchemaTests(unittest.TestCase):
    def test_email_draft_schema_valid_from_run_dir(self):
        with tempfile.TemporaryDirectory() as d:
            run_dir = Path(d) / "run"
            draft_dir = Path(d) / "draft"
            run = run_72h_dry_run_pipeline("examples/sample_inputs", output_dir=run_dir)
            draft = build_email_draft(run["artifacts"]["output_dir"], output_dir=draft_dir)
            self.assertTrue(validate_json(draft, "email_draft"))
            self.assertTrue(draft["draft_only"])
            self.assertTrue(draft["requires_human_approval"])
            self.assertFalse(draft["external_delivery_sent"])
            self.assertEqual(draft["transport"]["mode"], "local_artifact_only")
            self.assertFalse(draft["transport"]["smtp_used"])
            self.assertFalse(draft["transport"]["sendmail_used"])
            self.assertFalse(draft["transport"]["webhook_used"])
            self.assertFalse(draft["transport"]["network_used"])
            self.assertFalse(draft["approval"]["approved"])


if __name__ == "__main__":
    unittest.main()
