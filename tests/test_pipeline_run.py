import json
import tempfile
import unittest
from pathlib import Path

from zyw_insight.pipeline import run_72h_dry_run_pipeline
from zyw_insight.schema_validation import validate_json


class PipelineRunTests(unittest.TestCase):
    def test_run_72h_dry_run_pipeline_schema_valid_and_artifacts(self):
        with tempfile.TemporaryDirectory() as d:
            run = run_72h_dry_run_pipeline("examples/sample_inputs", output_dir=d, spent_usd=50)
            self.assertTrue(validate_json(run, "pipeline_run"))
            self.assertTrue(run["dry_run"])
            boundary = run["runtime_boundary"]
            self.assertFalse(boundary["real_openrouter_call_executed"])
            self.assertFalse(boundary["canary_real_call_executed"])
            self.assertFalse(boundary["network_request_sent"])
            self.assertFalse(boundary["api_key_read"])
            self.assertFalse(boundary["email_sent"])
            self.assertFalse(boundary["webhook_sent"])
            artifacts = run["artifacts"]
            self.assertTrue(artifacts["analyses"])
            self.assertTrue(artifacts["critics"])
            self.assertTrue(Path(artifacts["brief_json"]).exists())
            self.assertTrue(Path(artifacts["brief_markdown"]).exists())
            self.assertTrue(artifacts["adapter_runs"])
            self.assertTrue(Path(artifacts["manifest_path"]).exists())
            self.assertTrue(Path(artifacts["ledger_path"]).exists())

    def test_brief_md_and_ledger_are_redacted(self):
        with tempfile.TemporaryDirectory() as d:
            run = run_72h_dry_run_pipeline("examples/sample_inputs", output_dir=d, spent_usd=50)
            markdown = Path(run["artifacts"]["brief_markdown"]).read_text(encoding="utf-8")
            self.assertIn("DRAFT ONLY", markdown)
            self.assertIn("Human Approval Required", markdown)
            for forbidden in ("API key", "token", "secret", "Authorization", "env"):
                self.assertNotIn(forbidden, markdown)
            ledger = Path(run["artifacts"]["ledger_path"]).read_text(encoding="utf-8")
            self.assertNotIn("body", ledger)
            self.assertNotIn("messages", ledger)
            for forbidden in ("api_key", "token", "secret", "env"):
                self.assertNotIn(forbidden, ledger.lower())

    def test_max_documents_limits_processed_count(self):
        with tempfile.TemporaryDirectory() as d:
            run = run_72h_dry_run_pipeline("examples/sample_inputs", output_dir=d, max_documents=1, spent_usd=410, trigger="openclaw_cron_dry_run")
            self.assertLessEqual(run["input"]["processed_document_count"], 1)
            self.assertTrue(run["input"]["skipped_documents"])
            self.assertEqual(run["trigger"], "openclaw_cron_dry_run")
            self.assertTrue(any(item["rule_id"] == "volume_reduction" for item in run["guardrail_results"]))

    def test_manifest_does_not_include_source_body(self):
        with tempfile.TemporaryDirectory() as d:
            run = run_72h_dry_run_pipeline("examples/sample_inputs", output_dir=d, spent_usd=50)
            manifest = json.loads(Path(run["artifacts"]["manifest_path"]).read_text(encoding="utf-8"))
            self.assertNotIn("body", json.dumps(manifest).lower())


if __name__ == "__main__":
    unittest.main()
