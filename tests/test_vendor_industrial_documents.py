import json
import subprocess
import sys
import unittest
from pathlib import Path

from zyw_insight.analyzer import analyze_source
from zyw_insight.critic import critique_analysis
from zyw_insight.ingestion import ingest_file
from zyw_insight.schema_validation import validate_json
from zyw_insight.triage import triage_source


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/sample_inputs/vendor_industrial_high_trust.md"


class VendorIndustrialDocumentTests(unittest.TestCase):
    def test_high_trust_industrial_fixture_triages_as_deep_read_candidate(self):
        source = ingest_file(FIXTURE)
        triage = triage_source(source)
        self.assertIn(triage["document_type"], {"industrial_report", "engineering_report", "production_report"})
        self.assertIn(triage["source_tier"], {"A", "B"})
        self.assertEqual(triage["deep_read_priority"], "High")
        self.assertIn("vendor_claim", triage["risk_flags"])

    def test_analyze_and_critique_do_not_require_paper_type(self):
        source = ingest_file(FIXTURE)
        triage = triage_source(source)
        analysis = analyze_source(source, triage)
        critic = critique_analysis(analysis)
        self.assertTrue(validate_json(analysis, "literature_analysis"))
        self.assertTrue(validate_json(critic, "constraint_critic"))
        self.assertIn(analysis["basic_info"]["document_type"], {"industrial_report", "engineering_report", "production_report"})
        self.assertIn("vendor_claim", analysis["risk_flags"])
        self.assertNotEqual(analysis["conclusion_strength"], "strong")

    def test_cli_ingest_triage_analyze_critique_accept_fixture(self):
        for command in ("ingest", "triage", "analyze", "critique"):
            proc = subprocess.run(
                [sys.executable, "-m", "zyw_insight.cli", command, str(FIXTURE), "--pretty"] if command in {"analyze", "critique"} else [sys.executable, "-m", "zyw_insight.cli", command, str(FIXTURE)],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(proc.stdout)
            self.assertIsInstance(payload, dict)


if __name__ == "__main__":
    unittest.main()
