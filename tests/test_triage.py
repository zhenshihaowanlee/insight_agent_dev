import json
import subprocess
import sys
import unittest
from pathlib import Path

from zyw_insight.ingestion import ingest_file
from zyw_insight.triage import triage_source


ROOT = Path(__file__).resolve().parents[1]


class TriageTests(unittest.TestCase):
    def test_high_credibility_paper_gets_high_or_medium(self):
        result = triage_source(ingest_file(ROOT / "examples/sample_inputs/sample_paper.md"))
        self.assertIn(result["deep_read_priority"], {"High", "Medium"})
        self.assertIn(result["source_tier"], {"A", "B"})
        self.assertIn(result["domain"], {"datacenter networking", "RDMA / RoCE", "congestion control", "AI cluster networking"})

    def test_vendor_marketing_gets_low_or_medium_with_risks(self):
        result = triage_source(ingest_file(ROOT / "examples/sample_inputs/vendor_whitepaper.txt"))
        self.assertIn(result["deep_read_priority"], {"Low", "Medium"})
        self.assertIn("vendor_claim", result["risk_flags"])
        self.assertIn("marketing_language", result["risk_flags"])

    def test_cli_triage_returns_json(self):
        proc = subprocess.run(
            [sys.executable, "-m", "zyw_insight.cli", "triage", str(ROOT / "examples/sample_inputs/sample_paper.md")],
            cwd=ROOT,
            env={"PYTHONPATH": "src"},
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertIn("deep_read_priority", payload)
        self.assertIn("risk_flags", payload)


if __name__ == "__main__":
    unittest.main()
