import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from zyw_insight.analyzer import NETWORK_KEYS, analyze_source
from zyw_insight.brief import synthesize_brief
from zyw_insight.critic import critique_analysis
from zyw_insight.ingestion import ingest_file
from zyw_insight.schema_validation import validate_json
from zyw_insight.triage import triage_source


ROOT = Path(__file__).resolve().parents[1]


def combined_sample(name):
    source = ingest_file(ROOT / f"examples/sample_inputs/{name}")
    analysis = analyze_source(source, triage_source(source))
    critic = critique_analysis(analysis)
    return {"analysis": analysis, "critic": critic}


class BriefTests(unittest.TestCase):
    def test_synthesize_brief_schema_valid(self):
        brief = synthesize_brief([combined_sample("sample_paper.md"), combined_sample("vendor_whitepaper.txt")])
        self.assertTrue(validate_json(brief, "brief"))

    def test_brief_contains_executive_brief(self):
        brief = synthesize_brief([combined_sample("sample_paper.md"), combined_sample("vendor_whitepaper.txt")])
        self.assertIn("top_conclusions", brief["executive_brief"])

    def test_brief_contains_signal_radar(self):
        brief = synthesize_brief([combined_sample("sample_paper.md"), combined_sample("vendor_whitepaper.txt")])
        self.assertTrue(brief["technology_signal_radar"])

    def test_brief_contains_cross_document_conflicts(self):
        brief = synthesize_brief([combined_sample("sample_paper.md"), combined_sample("vendor_whitepaper.txt")])
        self.assertIn("cross_document_conflicts", brief)

    def test_brief_contains_process_constraint_trends(self):
        brief = synthesize_brief([combined_sample("sample_paper.md"), combined_sample("vendor_whitepaper.txt")])
        self.assertIn("most_frequent_constraints", brief["process_constraint_trends"])

    def test_network_metric_trends_has_9_dimensions(self):
        brief = synthesize_brief([combined_sample("sample_paper.md"), combined_sample("vendor_whitepaper.txt")])
        self.assertEqual(set(brief["network_metric_trends"]), set(NETWORK_KEYS))

    def test_draft_delivery_is_draft_only(self):
        brief = synthesize_brief([combined_sample("sample_paper.md")])
        self.assertEqual(brief["draft_delivery"]["mode"], "draft_only")
        self.assertIs(brief["draft_delivery"]["requires_human_approval"], True)

    def test_less_than_two_inputs_warns_weak_cross_document(self):
        brief = synthesize_brief([combined_sample("sample_paper.md")])
        self.assertTrue(any("cross-document signal is weak" in item for item in brief["executive_brief"]["top_conclusions"]))

    def test_vendor_heavy_inputs_raise_biggest_risk(self):
        brief = synthesize_brief([combined_sample("vendor_whitepaper.txt"), combined_sample("vendor_whitepaper.txt")])
        self.assertTrue(any("vendor/marketing/no experiment" in item for item in brief["executive_brief"]["biggest_risks"]))

    def test_cli_brief_outputs_json(self):
        with tempfile.TemporaryDirectory() as d:
            input_dir = Path(d) / "inputs"
            input_dir.mkdir()
            (input_dir / "one.json").write_text(json.dumps(combined_sample("sample_paper.md")), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "zyw_insight.cli", "brief", str(input_dir)],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(proc.stdout)
            self.assertIn("executive_brief", payload)

    def test_cli_brief_output_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            input_dir = Path(d) / "inputs"
            input_dir.mkdir()
            (input_dir / "one.json").write_text(json.dumps(combined_sample("sample_paper.md")), encoding="utf-8")
            output = Path(d) / "brief.json"
            subprocess.run(
                [sys.executable, "-m", "zyw_insight.cli", "brief", str(input_dir), "--output", str(output)],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("draft_delivery", payload)


if __name__ == "__main__":
    unittest.main()
