import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OpenClawPreSendReviewTemplateTests(unittest.TestCase):
    def test_pre_send_review_templates_are_safe(self):
        paths = [
            ROOT / "openclaw/harness/cron/zyw_pre_send_review_dry_run.prompt.md",
            ROOT / "openclaw/harness/cron/zyw_pre_send_review_dry_run.config.json5",
        ]
        forbidden = ["smtp", "sendmail", "webhook", "curl", "OPENROUTER_API_KEY", "--real-call"]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn("pre-send-review", text)
            for marker in forbidden:
                self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
