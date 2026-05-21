import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from zyw_insight.analyzer import analyze_source
from zyw_insight.critic import critique_analysis
from zyw_insight.ingestion import ingest_file
from zyw_insight.schema_validation import validate_json
from zyw_insight.triage import triage_source


ROOT = Path(__file__).resolve().parents[1]


def analyzed_sample(name: str):
    source = ingest_file(ROOT / f"examples/sample_inputs/{name}")
    return analyze_source(source, triage_source(source))


class CriticTests(unittest.TestCase):
    def test_sample_paper_critique_schema_valid(self):
        critic = critique_analysis(analyzed_sample("sample_paper.md"))
        self.assertTrue(validate_json(critic, "constraint_critic"))

    def test_vendor_whitepaper_critique_schema_valid(self):
        critic = critique_analysis(analyzed_sample("vendor_whitepaper.txt"))
        self.assertTrue(validate_json(critic, "constraint_critic"))

    def test_vendor_whitepaper_not_s_or_a(self):
        critic = critique_analysis(analyzed_sample("vendor_whitepaper.txt"))
        self.assertNotIn(critic["recommended_action_after"], {"S", "A"})

    def test_vendor_whitepaper_has_vendor_marketing_no_experiment_reasons(self):
        critic = critique_analysis(analyzed_sample("vendor_whitepaper.txt"))
        joined = " ".join(critic["downgrade_reasons"] + [item["rule_id"] for item in critic["hard_rule_violations"]])
        self.assertIn("vendor", joined)
        self.assertTrue("marketing" in joined or "no_experiment" in joined)

    def test_latency_strong_without_tail_is_flagged(self):
        analysis = analyzed_sample("sample_paper.md")
        analysis["network_impact_vector"]["latency"] = {
            "impact": "++",
            "evidence": "average latency only",
            "risk": "distribution not discussed",
        }
        critic = critique_analysis(analysis)
        rules = {item["rule_id"]: item["severity"] for item in critic["hard_rule_violations"]}
        self.assertIn(rules.get("latency_strong_without_tail"), {"warning", "major"})

    def test_degraded_process_conditions_missing_is_major(self):
        analysis = analyzed_sample("sample_paper.md")
        analysis["degraded_process_counterfactual"]["verdict"] = "conditional"
        analysis["degraded_process_counterfactual"]["conditions"] = []
        critic = critique_analysis(analysis)
        rules = {item["rule_id"]: item["severity"] for item in critic["hard_rule_violations"]}
        self.assertEqual(rules.get("degraded_process_conditions_missing"), "major")

    def test_score_after_total_is_0_to_100(self):
        critic = critique_analysis(analyzed_sample("vendor_whitepaper.txt"))
        self.assertGreaterEqual(critic["score_after"]["total_score"], 0)
        self.assertLessEqual(critic["score_after"]["total_score"], 100)

    def test_cli_critique_outputs_json(self):
        proc = subprocess.run(
            [sys.executable, "-m", "zyw_insight.cli", "critique", str(ROOT / "examples/sample_inputs/sample_paper.md")],
            cwd=ROOT,
            env={"PYTHONPATH": "src"},
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertIn("critic_id", payload)
        self.assertIn("hard_rule_violations", payload)

    def test_cli_critique_output_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "critic.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "zyw_insight.cli",
                    "critique",
                    str(ROOT / "examples/sample_inputs/vendor_whitepaper.txt"),
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
            self.assertIn("score_after", payload)


if __name__ == "__main__":
    unittest.main()
