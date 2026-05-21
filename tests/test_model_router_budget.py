import json
import subprocess
import sys
import unittest
from pathlib import Path

from zyw_insight.budget import load_budget_policy
from zyw_insight.model_router import choose_model_for_stage, validate_openrouter_model_id


ROOT = Path(__file__).resolve().parents[1]


class ModelRouterBudgetTests(unittest.TestCase):
    def test_low_priority_after_90_is_fallback_or_denied(self):
        decision = choose_model_for_stage(
            "literature_analysis",
            policy=load_budget_policy("quality_first"),
            spent_usd=410,
            triage_result={"source_tier": "D", "deep_read_priority": "Low"},
        )
        self.assertFalse(decision["processing_allowed"] and decision["selected_model"].endswith("long-context-analysis-placeholder"))

    def test_high_priority_after_90_preserves_quality_with_warning(self):
        decision = choose_model_for_stage(
            "literature_analysis",
            policy=load_budget_policy("quality_first"),
            spent_usd=410,
            triage_result={"source_tier": "A", "deep_read_priority": "High"},
        )
        self.assertEqual(decision["selected_model"], "openrouter/long-context-analysis-placeholder")
        self.assertEqual(decision["budget_warning"], "degrade_90")
        self.assertTrue(decision["quality_preserved"])

    def test_hard_cap_denies_processing(self):
        decision = choose_model_for_stage("literature_analysis", policy=load_budget_policy("quality_first"), spent_usd=600)
        self.assertFalse(decision["processing_allowed"])

    def test_final_review_manual_required(self):
        decision = choose_model_for_stage("final_review", policy=load_budget_policy("quality_first"), spent_usd=50)
        self.assertTrue(decision["manual_required"])
        self.assertFalse(decision["processing_allowed"])

    def test_forbidden_model_provider(self):
        with self.assertRaises(ValueError):
            validate_openrouter_model_id("openrouter/oauth-bad")

    def test_cli_route_model_outputs_json(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "zyw_insight.cli",
                "route-model",
                "literature_analysis",
                "--environment",
                "quality_first",
                "--spent-usd",
                "410",
                "--source-tier",
                "A",
                "--deep-read-priority",
                "High",
            ],
            cwd=ROOT,
            env={"PYTHONPATH": "src"},
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(proc.stdout)["budget_warning"], "degrade_90")


if __name__ == "__main__":
    unittest.main()
