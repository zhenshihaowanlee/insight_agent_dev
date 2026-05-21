import tempfile
import unittest
from pathlib import Path

from zyw_insight.budget_ledger import append_budget_event, load_budget_events, summarize_budget_events


class BudgetLedgerTests(unittest.TestCase):
    def test_ledger_does_not_record_body(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ledger.jsonl"
            append_budget_event(
                {
                    "stage": "triage",
                    "source_id": "s1",
                    "estimated_input_tokens": 100,
                    "estimated_output_tokens": 10,
                    "estimated_cost_usd": 0.01,
                    "model_id": "openrouter/low-cost-triage-placeholder",
                    "budget_status": "ok",
                    "quality_priority": "high",
                    "quality_preserved": True,
                    "dry_run": True,
                    "body": "must not be recorded",
                    "api_key": "must not be recorded",
                },
                path,
            )
            events = load_budget_events(path)
            self.assertNotIn("body", events[0])
            self.assertNotIn("api_key", events[0])
            summary = summarize_budget_events(events)
            self.assertFalse(summary["body_recorded"])


if __name__ == "__main__":
    unittest.main()
