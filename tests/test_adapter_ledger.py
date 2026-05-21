import json
import tempfile
import unittest
from pathlib import Path

from zyw_insight.budget_ledger import load_budget_events, summarize_budget_events
from zyw_insight.ingestion import ingest_file
from zyw_insight.openrouter_adapter import run_adapter_dry_run


ROOT = Path(__file__).resolve().parents[1]


class AdapterLedgerTests(unittest.TestCase):
    def test_redacted_ledger_excludes_sensitive_payload(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "ledger.jsonl"
            run_adapter_dry_run(
                "brief_synthesis",
                {"source_id": "s1", "body": "full body must not be logged", "messages": ["secret prompt"], "api_key": "bad"},
                write_ledger=True,
                ledger_path=ledger,
            )
            raw = ledger.read_text(encoding="utf-8")
            self.assertNotIn("full body", raw)
            self.assertNotIn("secret prompt", raw)
            self.assertNotIn("api_key", raw)
            events = load_budget_events(ledger)
            summary = summarize_budget_events(events)
            self.assertFalse(summary["body_recorded"])
            self.assertEqual(summary["event_count"], 1)

    def test_ledger_summary_counts(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "ledger.jsonl"
            run_adapter_dry_run(
                "literature_analysis",
                ingest_file(ROOT / "examples/sample_inputs/vendor_whitepaper.txt"),
                spent_usd=410,
                triage_result={"source_tier": "D", "deep_read_priority": "Low"},
                write_ledger=True,
                ledger_path=ledger,
            )
            summary = summarize_budget_events(load_budget_events(ledger))
            self.assertEqual(summary["count_denied"], 1)
            self.assertIn("degrade_90", summary["count_by_budget_status"])


if __name__ == "__main__":
    unittest.main()
