import tempfile
import unittest
from pathlib import Path

from zyw_insight.budget_ledger import load_budget_events
from zyw_insight.openrouter_canary import execute_openrouter_canary


class CanaryLedgerRedactionTests(unittest.TestCase):
    def test_canary_ledger_redacted(self):
        with tempfile.TemporaryDirectory() as d:
            ledger = Path(d) / "canary.jsonl"
            execute_openrouter_canary(
                "literature_analysis",
                {"source_id": "s1", "body": "full body text", "messages": ["full message"], "token": "secret"},
                "openrouter/example/model-slug",
                write_ledger=True,
                ledger_path=ledger,
            )
            raw = ledger.read_text(encoding="utf-8")
            self.assertNotIn("full body text", raw)
            self.assertNotIn("full message", raw)
            self.assertNotIn("secret", raw.lower())
            self.assertNotIn("reasoning", raw.lower())
            self.assertNotIn("authorization", raw.lower())
            self.assertNotIn("env", raw.lower())
            events = load_budget_events(ledger)
            self.assertEqual(len(events), 1)
            self.assertIs(events[0]["manual_required"], False)


if __name__ == "__main__":
    unittest.main()
