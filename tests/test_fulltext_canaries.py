import json
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

from zyw_insight.cross_validation import build_cross_validation_report
from zyw_insight.full_paper_canary import run_full_paper_canary, run_three_paper_fulltext_canary
from zyw_insight.fulltext_eligibility import evaluate_fulltext_eligibility, select_fulltext_candidates
from zyw_insight.fulltext_fetch import fetch_and_extract_fulltext
from zyw_insight.pdf_text_extract import extract_pdf_text
from zyw_insight.schema_validation import validate_json
from zyw_insight.source_discovery import _candidate


def a_candidate():
    return _candidate(
        "arxiv",
        "1234.5678v1",
        "SIGCOMM datacenter RDMA congestion control p99 baseline evaluation",
        "SIGCOMM datacenter RDMA congestion control experiment baseline p95 p99 measurement implementation.",
        venue="SIGCOMM",
        source_url="https://arxiv.org/abs/1234.5678",
        pdf_url="https://arxiv.org/pdf/1234.5678",
        document_type="paper",
    )


def c_candidate():
    return _candidate(
        "arxiv",
        "9999.9999v1",
        "arXiv datacenter congestion control preprint",
        "arXiv datacenter congestion control experiment baseline p99.",
        venue="arXiv",
        source_url="https://arxiv.org/abs/9999.9999",
        pdf_url="https://arxiv.org/pdf/9999.9999",
        document_type="paper",
    )


class FulltextCanaryTests(unittest.TestCase):
    def test_open_access_eligibility_allows_a_high_arxiv(self):
        result = evaluate_fulltext_eligibility(a_candidate())
        self.assertTrue(result["open_access"])
        self.assertTrue(result["fetch_allowed"])
        self.assertFalse(result["paywall_bypass"])
        self.assertTrue(validate_json(result, "fulltext_eligibility"))

    def test_rejects_non_open_access_pdf(self):
        candidate = a_candidate()
        candidate["pdf_url"] = "https://publisher.example.com/paper.pdf"
        result = evaluate_fulltext_eligibility(candidate)
        self.assertFalse(result["fetch_allowed"])
        self.assertIn("not an explicitly allowed", result["eligibility_reason"])

    def test_rejects_arbitrary_url_and_paywall_bypass(self):
        candidate = a_candidate()
        candidate["source_provider"] = "manual_watchlist"
        candidate["pdf_url"] = "https://example.com/free.pdf"
        result = evaluate_fulltext_eligibility(candidate)
        self.assertFalse(result["fetch_allowed"])
        self.assertFalse(result["runtime_boundary"]["paywall_bypass_enabled"])
        self.assertFalse(result["runtime_boundary"]["arbitrary_url_fetch_enabled"])

    def test_c_candidate_cannot_enter_fulltext_analysis(self):
        result = evaluate_fulltext_eligibility(c_candidate())
        self.assertFalse(result["fetch_allowed"])
        self.assertEqual(select_fulltext_candidates([c_candidate(), a_candidate()], 3)[0]["candidate"]["candidate_id"], a_candidate()["candidate_id"])

    def test_fulltext_artifact_schema_and_hash(self):
        candidate = a_candidate()
        eligibility = evaluate_fulltext_eligibility(candidate)

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, _size=-1):
                if getattr(self, "done", False):
                    return b""
                self.done = True
                return b"%PDF fake Abstract Method Evaluation References"

        with tempfile.TemporaryDirectory() as d:
            with mock.patch("urllib.request.urlopen", return_value=FakeResp()):
                artifact = fetch_and_extract_fulltext(candidate, eligibility, d, allow_network=True, dry_run=False)
            self.assertTrue(validate_json(artifact, "fulltext_artifact"))
            self.assertTrue(Path(artifact["extracted_text_path"]).exists())
            self.assertIsNotNone(artifact["extracted_text_sha256"])

    def test_pdf_stream_extractor_reads_text_not_raw_pdf_bytes(self):
        content = (
            b"BT /F1 12 Tf "
            b"[(Abstract)-120(MegaScale)-120(Method)-120(architecture)-120(Evaluation)-120(results)-120(Limitations)]TJ "
            b"ET"
        )
        compressed = zlib.compress(content)
        pdf = f"%PDF-1.5\n1 0 obj << /Length {len(compressed)} /Filter /FlateDecode >> stream\n".encode("ascii")
        pdf += compressed + b"\nendstream endobj\n%%EOF\n"
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "paper.pdf")
            path.write_bytes(pdf)
            extracted = extract_pdf_text(path, max_pages=5, max_chars=1000)
        self.assertEqual(extracted["extractor"], "pdf_streams")
        self.assertFalse(extracted["text"].startswith("%PDF"))
        self.assertIn("Abstract", extracted["text"])
        self.assertTrue(extracted["section_hints"]["abstract"])
        self.assertTrue(extracted["section_hints"]["method_or_design"])
        self.assertTrue(extracted["section_hints"]["evaluation_or_experiments"])

    def test_one_paper_canary_dry_run_with_fake_discovery(self):
        fake_discovery = {"candidates": [a_candidate()], "provider_errors": []}
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("zyw_insight.full_paper_canary.discover_sources", return_value=fake_discovery):
                result = run_full_paper_canary(output_dir=d, providers=["arxiv"])
            self.assertFalse(result["real_call_executed"])
            self.assertTrue(Path(d, "fulltext_eligibility.json").exists())
            self.assertTrue(Path(d, "manifest.json").exists())

    def test_three_paper_canary_dry_run_and_cross_schema(self):
        fake_discovery = {"candidates": [a_candidate(), a_candidate(), a_candidate(), c_candidate()], "provider_errors": []}
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("zyw_insight.full_paper_canary.discover_sources", return_value=fake_discovery):
                result = run_three_paper_fulltext_canary(output_dir=d, providers=["arxiv"], max_papers=3)
            self.assertLessEqual(result["selected_paper_count"], 3)
            report = json.loads(Path(result["artifacts"]["cross_validation_report_json"]).read_text(encoding="utf-8"))
            self.assertTrue(validate_json(report, "cross_validation_report"))
            self.assertFalse(report["validation"]["claims_full_paper_cross_validation"])

    def test_cross_validation_marks_partial_extraction_limitations(self):
        report = build_cross_validation_report([{"candidate_id": "c1", "analysis": {}, "fulltext_artifact": {"section_hints": {}}}])
        self.assertIn("partial", " ".join(report["limitations"]))
        self.assertFalse(report["validation"]["claims_full_paper_cross_validation"])


if __name__ == "__main__":
    unittest.main()
