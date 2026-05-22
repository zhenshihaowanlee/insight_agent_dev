import unittest
from unittest import mock

from zyw_insight.source_discovery import discover_sources


class RealNetworkDiscoveryCapabilityTests(unittest.TestCase):
    def test_runtime_boundary_marks_metadata_network_without_model_or_delivery(self):
        fake = {
            "candidate_id": "cand-test",
            "discovered_at": "2026-05-22T00:00:00+00:00",
            "source_provider": "openalex",
            "provider_record_id": "https://openalex.org/W1",
            "title": "SIGCOMM datacenter networking measurement p99 baseline",
            "abstract": "Production datacenter networking measurement with baseline and p99.",
            "authors": [],
            "published_at": "2026",
            "updated_at": None,
            "venue": "SIGCOMM",
            "source_url": "https://openalex.org/W1",
            "pdf_url": None,
            "doi": None,
            "arxiv_id": None,
            "openalex_id": "https://openalex.org/W1",
            "semantic_scholar_id": None,
            "ietf_id": None,
            "document_type": "paper",
            "source_tier_hint": "A",
            "domain_hints": ["datacenter networking"],
            "credibility_hints": ["tier_hint_A", "evidence_signal"],
            "business_relevance_hints": ["target_domain"],
            "deep_read_priority_hint": "High",
            "keyword_matches": ["datacenter networking"],
            "dedup_keys": {"openalex_id": "https://openalex.org/w1", "title_hash": "x"},
            "body_is_untrusted": True,
            "provenance": {"provider": "openalex", "metadata_only": True, "pdf_downloaded": False, "fulltext_fetched": False},
            "metadata": {},
        }
        with mock.patch("zyw_insight.source_discovery.discover_provider", return_value=[fake]):
            run = discover_sources(providers=["openalex"], max_candidates=1)
        boundary = run["runtime_boundary"]
        self.assertTrue(run["network_used"])
        self.assertTrue(boundary["discovery_network_used"])
        self.assertFalse(boundary["model_network_used"])
        self.assertFalse(boundary["openrouter_called"])
        self.assertFalse(boundary["pdf_downloaded"])
        self.assertFalse(boundary["fulltext_fetched"])
        self.assertFalse(boundary["paywall_bypassed"])
        self.assertFalse(boundary["email_sent"])
        self.assertFalse(boundary["webhook_sent"])
        self.assertGreaterEqual(run["candidate_count"], 1)


if __name__ == "__main__":
    unittest.main()
