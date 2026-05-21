import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from zyw_insight.analyzer import NETWORK_KEYS, analyze_source
from zyw_insight.ingestion import ingest_file
from zyw_insight.triage import triage_source


ROOT = Path(__file__).resolve().parents[1]
CNI_KEYS = [
    "basic_info",
    "one_sentence_conclusion",
    "problem_background",
    "core_idea",
    "contributions",
    "mechanism",
    "process_constraints",
    "constraint_dependency_analysis",
    "degraded_process_counterfactual",
    "network_impact_vector",
    "evidence_quality",
    "comparison_with_existing_technology",
    "hidden_assumptions_and_risks",
    "security_and_operations_impact",
    "reproducibility",
    "technical_insights",
    "strategic_significance",
    "score",
    "recommended_action",
    "follow_up_validation_experiments",
]


class AnalyzerTests(unittest.TestCase):
    def analyze_sample(self, name):
        source = ingest_file(ROOT / f"examples/sample_inputs/{name}")
        return analyze_source(source, triage_source(source))

    def test_sample_paper_contains_cni_20_sections(self):
        analysis = self.analyze_sample("sample_paper.md")
        for key in CNI_KEYS:
            self.assertIn(key, analysis)
        self.assertIn(analysis["recommended_action"], {"A", "B"})

    def test_network_impact_vector_contains_9_dimensions(self):
        analysis = self.analyze_sample("sample_paper.md")
        self.assertEqual(set(analysis["network_impact_vector"]), set(NETWORK_KEYS))

    def test_score_total_is_0_to_100(self):
        analysis = self.analyze_sample("sample_paper.md")
        self.assertGreaterEqual(analysis["score"]["total_score"], 0)
        self.assertLessEqual(analysis["score"]["total_score"], 100)

    def test_body_is_untrusted_stays_true(self):
        analysis = self.analyze_sample("sample_paper.md")
        self.assertIs(analysis["body_is_untrusted"], True)

    def test_vendor_whitepaper_is_not_production_ready(self):
        analysis = self.analyze_sample("vendor_whitepaper.txt")
        self.assertIn(analysis["recommended_action"], {"B", "C", "D"})
        self.assertNotEqual(analysis["conclusion_strength"], "strong")
        self.assertLess(analysis["score"]["total_score"], 70)

    def test_vendor_quality_gates_include_risk(self):
        analysis = self.analyze_sample("vendor_whitepaper.txt")
        rules = {item["rule"] for item in analysis["quality_gate_results"]["issues"]}
        self.assertTrue({"no_experiment_no_strong_conclusion", "vendor_claim", "marketing_language"} & rules)

    def test_cli_analyze_returns_json(self):
        proc = subprocess.run(
            [sys.executable, "-m", "zyw_insight.cli", "analyze", str(ROOT / "examples/sample_inputs/sample_paper.md")],
            cwd=ROOT,
            env={"PYTHONPATH": "src"},
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertIn("network_impact_vector", payload)
        self.assertTrue(payload["body_is_untrusted"])

    def test_cli_analyze_output_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "analysis.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "zyw_insight.cli",
                    "analyze",
                    str(ROOT / "examples/sample_inputs/sample_paper.md"),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("basic_info", payload)


if __name__ == "__main__":
    unittest.main()
