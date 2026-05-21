import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OpenClawEmailDraftTemplateTests(unittest.TestCase):
    def test_email_draft_templates_are_local_only(self):
        paths = [
            ROOT / "openclaw/harness/cron/zyw_email_draft_dry_run.prompt.md",
            ROOT / "openclaw/harness/cron/zyw_email_draft_dry_run.config.json5",
        ]
        forbidden = ["smtp", "sendmail", "webhook", "curl", "OPENROUTER_API_KEY", "--real-call"]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn("email-draft", text)
            for marker in forbidden:
                self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
