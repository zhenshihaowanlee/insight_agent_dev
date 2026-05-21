import tempfile
import unittest
from pathlib import Path

from zyw_insight.email_draft import SAFE_REVIEW_RECIPIENT, build_email_draft
from zyw_insight.pipeline import run_72h_dry_run_pipeline


class EmailDraftTests(unittest.TestCase):
    def _run_dir(self, root: Path) -> str:
        return run_72h_dry_run_pipeline("examples/sample_inputs", output_dir=root / "run")["artifacts"]["output_dir"]

    def test_build_email_draft_artifacts_and_defaults(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            draft = build_email_draft(self._run_dir(root), output_dir=root / "draft")
            self.assertEqual(draft["headers"]["to"], [SAFE_REVIEW_RECIPIENT])
            self.assertTrue(draft["headers"]["subject"].startswith("[DRAFT][ZYW Insight][Review Required]"))
            self.assertTrue(Path(draft["body"]["eml_path"]).exists())
            self.assertTrue(Path(draft["body"]["markdown_path"]).exists())
            self.assertTrue(Path(draft["approval"]["approval_checklist_path"]).exists())
            self.assertTrue((root / "draft" / "email_draft_manifest.json").exists())

    def test_draft_content_has_no_sensitive_or_transport_markers(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            draft = build_email_draft(self._run_dir(root), output_dir=root / "draft")
            combined = Path(draft["body"]["eml_path"]).read_text(encoding="utf-8") + Path(draft["body"]["markdown_path"]).read_text(encoding="utf-8")
            self.assertIn("Not production recommendation.", combined)
            for marker in ("OPENROUTER_API_KEY", "Authorization", "Bearer", "sk-", "token", "secret", "smtp", "sendmail", "webhook"):
                self.assertNotIn(marker, combined)

    def test_real_recipient_requires_explicit_flag_but_never_sends(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_dir = self._run_dir(root)
            with self.assertRaises(ValueError):
                build_email_draft(run_dir, output_dir=root / "blocked", to="real@example.com")
            draft = build_email_draft(run_dir, output_dir=root / "allowed", to="real@example.com", allow_real_recipient=True)
            self.assertEqual(draft["headers"]["to"], ["real@example.com"])
            self.assertFalse(draft["transport"]["network_used"])
            self.assertFalse(draft["runtime_boundary"]["email_sent"])


if __name__ == "__main__":
    unittest.main()
