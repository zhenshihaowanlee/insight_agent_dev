import unittest

from zyw_insight.schema_validation import validate_json
from zyw_insight.source_discovery import discover_sources


class DiscoveryRunSchemaTests(unittest.TestCase):
    def test_discovery_dry_run_schema_valid(self):
        run = discover_sources(dry_run=True)
        self.assertTrue(validate_json(run, "discovery_run"))
        self.assertFalse(run["runtime_boundary"]["model_network_used"])
        self.assertFalse(run["runtime_boundary"]["openrouter_called"])
        self.assertFalse(run["runtime_boundary"]["pdf_downloaded"])
        self.assertFalse(run["runtime_boundary"]["fulltext_fetched"])
        self.assertFalse(run["runtime_boundary"]["paywall_bypassed"])


if __name__ == "__main__":
    unittest.main()
