import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from zyw_insight.discovery_pipeline import materialize_selected_candidates, run_discovery_72h_dry_run
from zyw_insight.source_discovery import _candidate


ROOT = Path(__file__).resolve().parents[1]


def _a_candidate():
    return _candidate(
        "ietf",
        "rfc-test",
        "RFC test datacenter RDMA congestion control baseline p99 measurement",
        "IETF RFC datacenter RDMA congestion control measurement baseline p95 p99 deployment.",
        venue="IETF",
        source_url="https://datatracker.ietf.org/doc/rfc-test/",
        document_type="rfc",
    )


def _c_candidate():
    return _candidate(
        "arxiv",
        "2401.00001",
        "arXiv datacenter RDMA congestion control preprint",
        "arXiv preprint datacenter RDMA congestion control measurement baseline p99.",
        venue="arXiv",
        source_url="https://arxiv.org/abs/2401.00001",
        document_type="paper",
    )


class DiscoveryPipelineTests(unittest.TestCase):
    def test_materialize_selected_candidates_blocks_c_tier(self):
        a = _a_candidate()
        c = _c_candidate()
        discovery_run = {"candidates": [a, c]}
        watchlist = {
            "selected_for_deep_read": [
                {"candidate_id": a["candidate_id"]},
                {"candidate_id": c["candidate_id"]},
            ]
        }
        with tempfile.TemporaryDirectory() as d:
            result = materialize_selected_candidates(discovery_run, watchlist, d, max_selected=5)
            self.assertEqual(result["materialized_count"], 1)
            self.assertEqual(result["materialized"][0]["candidate_id"], a["candidate_id"])
            self.assertEqual(result["blocked"][0]["candidate_id"], c["candidate_id"])

    def test_materialized_stub_contains_untrusted_metadata_notice(self):
        a = _a_candidate()
        discovery_run = {"candidates": [a]}
        watchlist = {"selected_for_deep_read": [{"candidate_id": a["candidate_id"]}]}
        with tempfile.TemporaryDirectory() as d:
            result = materialize_selected_candidates(discovery_run, watchlist, d, max_selected=1)
            stub = Path(result["materialized"][0]["stub_path"]).read_text(encoding="utf-8")
            self.assertIn("UNTRUSTED METADATA ONLY", stub)
            self.assertIn("No full text fetched", stub)
            self.assertIn("No PDF downloaded", stub)
            self.assertIn("Not sufficient for strong conclusion", stub)
            self.assertIn("body_is_untrusted: true", stub)

    def test_run_discovery_72h_dry_run_creates_brief_and_manifest(self):
        fake_discovery = {
            "discovery_run_id": "disc-test",
            "created_at": "2026-05-21T00:00:00+00:00",
            "dry_run": False,
            "network_used": True,
            "real_metadata_discovery": True,
            "providers_requested": ["ietf"],
            "providers_executed": ["ietf"],
            "query_profile": "datacenter_networking",
            "candidate_count": 1,
            "deduplicated_count": 0,
            "selected_for_triage_count": 1,
            "selected_for_deep_read_count": 1,
            "candidates": [_a_candidate()],
            "deduplication_report": {"duplicates": []},
            "watchlist": {"selected_for_deep_read": [], "signal_only": [], "background_only": []},
            "triage_preview": [],
            "provider_errors": [],
            "runtime_boundary": {
                "codex_runtime_used": False,
                "openrouter_called": False,
                "network_request_sent": True,
                "discovery_network_used": True,
                "model_network_used": False,
                "pdf_downloaded": False,
                "fulltext_fetched": False,
                "paywall_bypassed": False,
                "email_sent": False,
                "webhook_sent": False,
            },
            "validation": {"schema_valid": True, "metadata_only": True},
            "notes": ["metadata-only source discovery; no PDF download, fulltext fetch, model call, or delivery"],
        }
        with tempfile.TemporaryDirectory() as d:
            with mock.patch("zyw_insight.discovery_pipeline.discover_sources", return_value=fake_discovery):
                result = run_discovery_72h_dry_run(output_dir=d, providers=["ietf"], max_candidates=1, max_selected=1)
            self.assertTrue(Path(d, "brief.md").exists())
            self.assertTrue(Path(d, "brief.json").exists())
            self.assertTrue(Path(d, "brief", "brief.md").exists())
            self.assertTrue(Path(d, "run_manifest.json").exists())
            manifest = json.loads(Path(d, "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["candidate_to_pipeline_input"]), 1)
            self.assertTrue(Path(manifest["candidate_to_pipeline_input"][0]["stub_path"]).exists())
            self.assertFalse(result["runtime_boundary"]["openrouter_called"])

    def test_cli_run_discovery_72h_dry_run_command_exists(self):
        proc = subprocess.run(
            [sys.executable, "-m", "zyw_insight.cli", "run-discovery-72h-dry-run", "--help"],
            cwd=ROOT,
            env={"PYTHONPATH": "src"},
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("--query-profile", proc.stdout)
        self.assertIn("--max-selected", proc.stdout)


if __name__ == "__main__":
    unittest.main()
