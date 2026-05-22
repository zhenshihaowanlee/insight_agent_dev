import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from zyw_insight.full_paper_canary import run_full_paper_canary
from zyw_insight.source_discovery import _candidate


def candidate():
    return _candidate(
        "arxiv",
        "2504.02263v1",
        "MegaScale-Infer: Serving Mixture-of-Experts at Scale with Disaggregated Expert Parallelism",
        "SIGCOMM 2025 AI cluster networking GPU communication M2N evaluation baseline p95 p99 implementation.",
        venue="SIGCOMM 2025",
        source_url="https://arxiv.org/abs/2504.02263",
        pdf_url="https://arxiv.org/pdf/2504.02263",
        arxiv_id="2504.02263v1",
        document_type="paper",
    )


class FullPaperCanaryOneShotTests(unittest.TestCase):
    def fake_artifact(self, text_path: Path):
        text = text_path.read_text(encoding="utf-8")
        return {
            "artifact_id": "fulltext-test",
            "candidate_id": candidate()["candidate_id"],
            "status": "extracted",
            "pdf_path": None,
            "extracted_text_path": str(text_path),
            "extracted_text_sha256": "sha",
            "extracted_char_count": len(text),
            "page_count": 1,
            "section_hints": {"abstract": True, "method_or_design": True, "evaluation_or_experiments": True},
            "extraction_quality": "partial_or_unverified",
            "source_url": "https://arxiv.org/abs/2504.02263",
            "pdf_url": "https://arxiv.org/pdf/2504.02263",
            "open_access": True,
            "paywall_bypassed": False,
            "body_is_untrusted": True,
            "runtime_boundary": {"open_access_only": True, "max_pdf_bytes_enforced": True, "max_pages_enforced": True, "max_extracted_chars_enforced": True, "ocr_used": False, "paywall_bypassed": False, "credentials_used": False, "body_logged_to_ledger": False, "codex_runtime_used": False},
        }

    def test_dry_run_writes_prompt_audit_and_redacts_request(self):
        with tempfile.TemporaryDirectory() as d:
            text_path = Path(d) / "paper.txt"
            text_path.write_text("Abstract method evaluation p95 p99 GPU communication. " * 1200, encoding="utf-8")
            with mock.patch("zyw_insight.full_paper_canary.discover_sources", return_value={"candidates": [candidate()], "provider_errors": []}), mock.patch("zyw_insight.full_paper_canary.fetch_and_extract_fulltext", return_value=self.fake_artifact(text_path)):
                result = run_full_paper_canary(output_dir=d, one_shot_fulltext=True, allow_fulltext_prompt=True, min_input_tokens_required=8000, target_input_tokens=18000, max_input_tokens=28000, max_output_tokens=5000, max_total_tokens=35000, fail_if_input_under_min=True, require_schema_valid_output=True)
            audit = json.loads(Path(d, "fulltext_prompt_audit.json").read_text(encoding="utf-8"))
            canary = json.loads(Path(d, "redacted_canary.json").read_text(encoding="utf-8"))
            raw = Path(d, "redacted_canary.json").read_text(encoding="utf-8")
            self.assertGreaterEqual(audit["estimated_input_tokens"], 8000)
            self.assertLessEqual(audit["conservative_estimated_input_tokens"], 28000)
            self.assertEqual(canary["request"]["requested_max_output_tokens"], 5000)
            self.assertTrue(canary["request"]["messages_redacted"])
            self.assertNotIn("Abstract method evaluation", raw)
            self.assertFalse(result["real_call_executed"])

    def test_low_actual_tokens_mark_full_text_not_really_sent(self):
        with tempfile.TemporaryDirectory() as d:
            text_path = Path(d) / "paper.txt"
            text_path.write_text("Abstract method evaluation p95 p99 GPU communication. " * 1200, encoding="utf-8")
            fake_canary = {
                "request": {"messages_sha256": "abc"},
                "response": {"status": "success"},
                "usage": {"actual_input_tokens": 100, "actual_output_tokens": 100},
                "cost": {"actual_cost_usd": 0.01},
                "real_call_executed": True,
            }
            with mock.patch("zyw_insight.full_paper_canary.discover_sources", return_value={"candidates": [candidate()], "provider_errors": []}), mock.patch("zyw_insight.full_paper_canary.fetch_and_extract_fulltext", return_value=self.fake_artifact(text_path)), mock.patch("zyw_insight.full_paper_canary._model_availability", return_value={"available": True, "internal_model_id": "openrouter/qwen/qwen3.5-397b-a17b", "api_model_slug": "qwen/qwen3.5-397b-a17b"}), mock.patch("zyw_insight.full_paper_canary.execute_openrouter_one_shot_fulltext", return_value={"canary": fake_canary, "parsed_analysis": None}):
                run_full_paper_canary(output_dir=d, one_shot_fulltext=True, allow_fulltext_prompt=True, real_call=True, allow_network=True, confirm_charge=True, min_input_tokens_required=8000, target_input_tokens=18000, max_input_tokens=28000, max_output_tokens=5000, max_total_tokens=35000, fail_if_input_under_min=True, require_schema_valid_output=True)
            analysis_run = json.loads(Path(d, "full_paper_analysis_run.json").read_text(encoding="utf-8"))
            self.assertTrue(analysis_run["full_text_not_really_sent"])
            self.assertTrue(analysis_run["analysis_too_short_for_cni"])

    def test_actual_input_over_cap_is_tracked(self):
        with tempfile.TemporaryDirectory() as d:
            text_path = Path(d) / "paper.txt"
            text_path.write_text("Abstract method evaluation p95 p99 GPU communication. " * 1200, encoding="utf-8")
            fake_canary = {
                "request": {"messages_sha256": "abc"},
                "response": {"status": "success"},
                "usage": {"actual_input_tokens": 30001, "actual_output_tokens": 1600},
                "cost": {"actual_cost_usd": 0.01},
                "real_call_executed": True,
            }
            with mock.patch("zyw_insight.full_paper_canary.discover_sources", return_value={"candidates": [candidate()], "provider_errors": []}), mock.patch("zyw_insight.full_paper_canary.fetch_and_extract_fulltext", return_value=self.fake_artifact(text_path)), mock.patch("zyw_insight.full_paper_canary._model_availability", return_value={"available": True, "internal_model_id": "openrouter/qwen/qwen3.5-397b-a17b", "api_model_slug": "qwen/qwen3.5-397b-a17b"}), mock.patch("zyw_insight.full_paper_canary.execute_openrouter_one_shot_fulltext", return_value={"canary": fake_canary, "parsed_analysis": None}):
                run_full_paper_canary(output_dir=d, one_shot_fulltext=True, allow_fulltext_prompt=True, real_call=True, allow_network=True, confirm_charge=True, min_input_tokens_required=8000, target_input_tokens=18000, max_input_tokens=28000, max_output_tokens=5000, max_total_tokens=35000, fail_if_input_under_min=True)
            analysis_run = json.loads(Path(d, "full_paper_analysis_run.json").read_text(encoding="utf-8"))
            self.assertTrue(analysis_run["actual_input_over_max_input_hard"])


if __name__ == "__main__":
    unittest.main()
