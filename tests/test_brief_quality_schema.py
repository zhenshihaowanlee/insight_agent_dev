import json
import subprocess
import sys
import unittest
from pathlib import Path

from zyw_insight.brief import synthesize_brief
from zyw_insight.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]


def load_samples():
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((ROOT / "examples/sample_brief_inputs").glob("*.json"))]


class BriefQualitySchemaTests(unittest.TestCase):
    def test_brief_quality_fields_present(self):
        brief = synthesize_brief(load_samples(), budget_mode="quality_first", quality_priority="high")
        self.assertEqual(brief["schema_version"], "brief.v1.1-quality-first")
        self.assertIn("input_traceability", brief)
        self.assertIn("insight_quality", brief)
        self.assertIn("decision_readiness", brief)
        self.assertIn("action_rationale", brief)
        self.assertIn("budget_context", brief)
        self.assertTrue(validate_json(brief, "brief"))

    def test_top_conclusions_are_traceable(self):
        brief = synthesize_brief(load_samples())
        joined = "\n".join(brief["executive_brief"]["top_conclusions"])
        self.assertTrue("source_id=" in joined or "critic_id=" in joined)

    def test_vendor_heavy_rejects_strong_claims(self):
        vendor = json.loads((ROOT / "examples/sample_brief_inputs/vendor_marketing_analysis_critic.json").read_text(encoding="utf-8"))
        brief = synthesize_brief([vendor, vendor])
        self.assertTrue(brief["insight_quality"]["rejected_strong_claims"])

    def test_cli_brief_quality_options(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "zyw_insight.cli",
                "brief",
                "examples/sample_brief_inputs",
                "--budget-mode",
                "quality_first",
                "--quality-priority",
                "high",
            ],
            cwd=ROOT,
            env={"PYTHONPATH": "src"},
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["budget_context"]["budget_mode"], "quality_first")


if __name__ == "__main__":
    unittest.main()
