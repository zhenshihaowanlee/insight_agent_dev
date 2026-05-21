import unittest
from unittest import mock

from zyw_insight.source_discovery import deduplicate_candidates, discover_provider, discover_sources


class SourceDiscoveryTests(unittest.TestCase):
    def test_no_network_dry_run(self):
        run = discover_sources(dry_run=False, network_enabled=False)
        self.assertFalse(run["network_used"])
        self.assertFalse(run["runtime_boundary"]["discovery_network_used"])

    def test_provider_allowlist_rejects_unknown(self):
        with self.assertRaises(ValueError):
            discover_sources(providers=["bad_provider"], dry_run=True)

    def test_deduplication_merges_doi(self):
        candidates = [
            {"candidate_id": "a", "title": "A", "dedup_keys": {"doi": "10/x"}},
            {"candidate_id": "b", "title": "B", "dedup_keys": {"doi": "10/x"}},
        ]
        result = deduplicate_candidates(candidates)
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["deduplicated_count"], 1)

    def test_discover_provider_uses_fake_query(self):
        with mock.patch("zyw_insight.source_discovery.query_arxiv", return_value=[]) as patched:
            result = discover_provider("arxiv", "datacenter_networking", 1, __import__("zyw_insight.source_registry").source_registry.load_source_discovery_config())
        self.assertEqual(result, [])
        self.assertTrue(patched.called)


if __name__ == "__main__":
    unittest.main()
