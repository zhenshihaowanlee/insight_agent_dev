import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OpenClawSourceDiscoveryTemplateTests(unittest.TestCase):
    def test_template_excludes_model_and_delivery_actions(self):
        for rel in (
            "openclaw/harness/cron/zyw_source_discovery_real_metadata.prompt.md",
            "openclaw/harness/cron/zyw_source_discovery_real_metadata.config.json5",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8").lower()
            for forbidden in ("openrouter_api_key", "--real-call", "openrouter-canary", "pipeline-canary --real-call", "smtp", "sendmail", "webhook", "download pdf", "pdf download"):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
