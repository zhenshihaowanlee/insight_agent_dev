import unittest
from unittest import mock

from zyw_insight.source_discovery import discover_sources


ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2504.02263v1</id>
    <updated>2025-04-03T00:00:00Z</updated>
    <published>2025-04-03T00:00:00Z</published>
    <title>MegaScale-Infer: Serving Mixture-of-Experts at Scale with Disaggregated Expert Parallelism</title>
    <summary>We present a distributed inference system for AI cluster networking, GPU communication, and M2N communication.</summary>
    <author><name>MegaScale Team</name></author>
    <link title="pdf" href="https://arxiv.org/pdf/2504.02263" rel="related" type="application/pdf"/>
  </entry>
</feed>
"""


class ArxivIdDiscoveryTests(unittest.TestCase):
    def test_arxiv_id_exact_discovery_enriches_megascale(self):
        with mock.patch("zyw_insight.source_discovery._request_text", return_value=ATOM):
            run = discover_sources(providers=["arxiv"], arxiv_id="2504.02263", max_candidates=1)
        self.assertTrue(run["network_used"])
        candidate = run["candidates"][0]
        self.assertIn("MegaScale-Infer", candidate["title"])
        self.assertEqual(candidate["source_provider"], "arxiv")
        self.assertEqual(candidate["pdf_url"], "https://arxiv.org/pdf/2504.02263")
        self.assertTrue(candidate["body_is_untrusted"])
        self.assertEqual(candidate["source_tier_hint"], "A")
        self.assertEqual(candidate["venue"], "SIGCOMM 2025")
        self.assertIn("AI cluster networking", candidate["domain_hints"])
        self.assertIn("distributed inference", candidate["domain_hints"])
        self.assertFalse(run["runtime_boundary"]["openrouter_called"])
        self.assertFalse(run["runtime_boundary"]["pdf_downloaded"])


if __name__ == "__main__":
    unittest.main()
