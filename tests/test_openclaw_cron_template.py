import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OpenClawCronTemplateTests(unittest.TestCase):
    def test_cron_dry_run_templates_are_safe(self):
        paths = [
            ROOT / "openclaw/harness/cron/zyw_72h_dry_run.prompt.md",
            ROOT / "openclaw/harness/cron/zyw_72h_dry_run.config.json5",
        ]
        forbidden = [
            "--real-call",
            "--allow-network",
            "--confirm-openrouter-charge",
            "OPENROUTER_API_KEY",
            "webhook",
            "smtp",
            "sendmail",
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertIn("run-72h-dry-run", text)
            for marker in forbidden:
                self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
