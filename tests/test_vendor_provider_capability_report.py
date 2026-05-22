import unittest

from zyw_insight.source_registry import PROVIDER_ALLOWLIST, FORBIDDEN_SOURCE_PATTERNS


class VendorProviderCapabilityReportTests(unittest.TestCase):
    def test_current_provider_allowlist_has_no_arbitrary_vendor_crawler(self):
        self.assertEqual(set(PROVIDER_ALLOWLIST), {"arxiv", "openalex", "crossref", "semantic_scholar", "ietf"})
        self.assertNotIn("web", PROVIDER_ALLOWLIST)
        self.assertNotIn("generic_url", PROVIDER_ALLOWLIST)
        self.assertNotIn("nvidia_docs", PROVIDER_ALLOWLIST)

    def test_policy_forbids_fulltext_paywall_style_sources(self):
        forbidden = " ".join(FORBIDDEN_SOURCE_PATTERNS)
        self.assertIn("paywall", forbidden)
        self.assertIn("download pdf", forbidden)
        self.assertIn("fulltext", forbidden)


if __name__ == "__main__":
    unittest.main()
