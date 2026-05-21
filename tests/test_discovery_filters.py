import unittest

from zyw_insight.discovery_filters import (
    detect_domain_hints,
    detect_source_tier_hint,
    extract_dedup_keys,
    select_for_deep_read,
)


class DiscoveryFiltersTests(unittest.TestCase):
    def test_domain_hints_detect_network_domains(self):
        text = "RDMA congestion control for SmartNIC optical fabric with SerDes BER FEC and P4"
        domains = detect_domain_hints(text)
        self.assertIn("RDMA / RoCE", domains)
        self.assertIn("P4 / programmable data plane", domains)
        self.assertIn("SmartNIC / DPU", domains)
        self.assertIn("optical interconnect", domains)
        self.assertIn("silicon / SerDes / BER / FEC", domains)

    def test_source_tier_rules(self):
        self.assertEqual(detect_source_tier_hint({"title": "SIGCOMM datacenter paper", "abstract": "", "venue": "SIGCOMM"}), "A")
        self.assertEqual(detect_source_tier_hint({"title": "arXiv datacenter paper", "abstract": "", "source_provider": "arxiv"}), "C")

    def test_dedup_keys(self):
        keys = extract_dedup_keys({"title": "A Paper", "doi": "10.1/X", "arxiv_id": "1234"})
        self.assertEqual(keys["doi"], "10.1/x")
        self.assertIn("title_hash", keys)

    def test_select_for_deep_read_only_a_b_high(self):
        candidates = [
            {"candidate_id": "a", "title": "A", "source_tier_hint": "A", "deep_read_priority_hint": "High", "domain_hints": ["RDMA / RoCE"]},
            {"candidate_id": "c", "title": "C", "source_tier_hint": "C", "deep_read_priority_hint": "High", "domain_hints": ["RDMA / RoCE"]},
        ]
        selected = select_for_deep_read(candidates, 10)
        self.assertEqual([item["candidate_id"] for item in selected], ["a"])


if __name__ == "__main__":
    unittest.main()
