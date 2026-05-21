import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OpenClawPipelineCanaryTemplateTests(unittest.TestCase):
    def test_pipeline_canary_templates_are_dry_run_only(self):
        for rel in (
            "openclaw/harness/cron/zyw_pipeline_canary_dry_run.prompt.md",
            "openclaw/harness/cron/zyw_pipeline_canary_dry_run.config.json5",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8").lower()
            for forbidden in ("--real-call", "--allow-network", "--confirm-openrouter-charge", "openrouter_api_key", "final_review", "smtp", "sendmail", "webhook", "curl"):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
