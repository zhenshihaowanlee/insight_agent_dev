import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from zyw_insight.full_paper_canary import run_full_paper_canary
from zyw_insight.source_discovery import _candidate


def megascale_candidate():
    return _candidate(
        "arxiv",
        "2504.02263v1",
        "MegaScale-Infer: Serving Mixture-of-Experts at Scale with Disaggregated Expert Parallelism",
        "SIGCOMM 2025 distributed inference AI cluster networking GPU communication M2N communication evaluation baseline p99.",
        ["MegaScale Team"],
        "2025-04-03T00:00:00Z",
        "2025-04-03T00:00:00Z",
        "SIGCOMM 2025",
        "https://arxiv.org/abs/2504.02263",
        "https://arxiv.org/pdf/2504.02263",
        arxiv_id="2504.02263v1",
        document_type="paper",
    )


class FullPaperCanaryArxivIdTests(unittest.TestCase):
    def test_arxiv_id_canary_dry_run_plans_pdf_and_no_model_call(self):
        fake_discovery = {"candidates": [megascale_candidate()], "provider_errors": []}
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("zyw_insight.full_paper_canary.discover_sources", return_value=fake_discovery) as mocked:
                result = run_full_paper_canary(arxiv_id="2504.02263", output_dir=d, providers=["arxiv"])
            mocked.assert_called_once()
            eligibility = json.loads(Path(d, "fulltext_eligibility.json").read_text(encoding="utf-8"))
            artifact = json.loads(Path(d, "fulltext", "fulltext_artifact.json").read_text(encoding="utf-8"))
            self.assertTrue(eligibility["fetch_allowed"])
            self.assertTrue(eligibility["pdf_download_allowed"])
            self.assertTrue(eligibility["open_access"])
            self.assertFalse(eligibility["paywall_bypass"])
            self.assertEqual(artifact["status"], "dry_run_planned")
            self.assertEqual(artifact["planned_pdf_url"], "https://arxiv.org/pdf/2504.02263")
            self.assertFalse(result["real_call_executed"])
            self.assertEqual(result["analysis_label"], "full_text_limited_analysis")


if __name__ == "__main__":
    unittest.main()
