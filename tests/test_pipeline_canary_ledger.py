import tempfile
import unittest
from pathlib import Path

from zyw_insight.budget_ledger import load_budget_events
from zyw_insight.pipeline_canary import run_small_pipeline_canary


class PipelineCanaryLedgerTests(unittest.TestCase):
    def test_pipeline_canary_ledger_redacted(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "pipeline_canary.real.jsonl"
            run_small_pipeline_canary(
                "examples/sample_inputs/sample_paper.md",
                output_dir=Path(d) / "run",
                ledger_path=ledger,
                write_ledger=True,
            )
            raw = ledger.read_text(encoding="utf-8")
            for forbidden in ("body", "messages", "content", "reasoning", "reasoning_details", "Authorization", "Bearer", "secret", "api_key"):
                self.assertNotIn(forbidden.lower(), raw.lower())
            events = load_budget_events(ledger)
            self.assertEqual(len(events), 1)
            self.assertIn("pipeline_canary_id", events[0])


if __name__ == "__main__":
    unittest.main()
