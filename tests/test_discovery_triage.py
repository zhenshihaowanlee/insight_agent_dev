import unittest

from zyw_insight.source_discovery import _candidate, build_watchlist
from zyw_insight.triage import triage_candidate_metadata


class DiscoveryTriageTests(unittest.TestCase):
    def test_a_b_high_enters_deep_read(self):
        candidate = _candidate("ietf", "rfc9999", "RFC RDMA datacenter congestion control", "experiment baseline p99 RDMA datacenter", [], "2026", None, "IETF", "https://datatracker.ietf.org/doc/rfc9999/", document_type="rfc")
        triage = triage_candidate_metadata(candidate)
        self.assertEqual(triage["source_tier"], "A")
        self.assertEqual(triage["deep_read_priority"], "High")
        watchlist = build_watchlist([candidate], [triage])
        self.assertTrue(watchlist["selected_for_deep_read"])

    def test_c_d_signal_background_only(self):
        c = _candidate("arxiv", "1", "arXiv RDMA signal", "RDMA datacenter", [], "2026", None, "arXiv", "u")
        d = _candidate("crossref", "2", "news summary", "overview", [], "2026", None, "news", "u", document_type="news")
        watchlist = build_watchlist([c, d])
        self.assertTrue(watchlist["signal_only"])
        self.assertTrue(watchlist["background_only"])


if __name__ == "__main__":
    unittest.main()
