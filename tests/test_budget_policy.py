import json
import subprocess
import sys
import unittest
from pathlib import Path

from zyw_insight.budget import get_budget_status, load_budget_policy, validate_budget_policy
from zyw_insight.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]


class BudgetPolicyTests(unittest.TestCase):
    def test_quality_first_policy_schema_valid(self):
        policy = load_budget_policy("quality_first")
        self.assertTrue(validate_json(policy, "budget_policy"))

    def test_budget_amounts(self):
        production = load_budget_policy("production")
        quality = load_budget_policy("quality_first")
        self.assertEqual(production["monthly_budget_usd"], 250)
        self.assertEqual(production["soft_cap_usd"], 300)
        self.assertEqual(production["hard_cap_usd"], 400)
        self.assertEqual(quality["monthly_budget_usd"], 350)
        self.assertEqual(quality["soft_cap_usd"], 450)
        self.assertEqual(quality["hard_cap_usd"], 600)

    def test_thresholds_and_model_ids(self):
        policy = load_budget_policy("quality_first")
        self.assertTrue({70, 90, 100}.issubset(set(policy["alert_thresholds"])))
        self.assertTrue(policy["priority_allocation"]["reduce_volume_before_model_quality"])
        for stage_policy in policy["stage_policies"].values():
            self.assertTrue(stage_policy["preferred_model"].startswith("openrouter/"))
            self.assertTrue(stage_policy["fallback_model"].startswith("openrouter/"))

    def test_forbidden_provider_rejected(self):
        policy = load_budget_policy("quality_first")
        policy = json.loads(json.dumps(policy))
        policy["stage_policies"]["triage"]["preferred_model"] = "openrouter/codex-bad"
        with self.assertRaises(ValueError):
            validate_budget_policy(policy)

    def test_budget_status_thresholds(self):
        policy = load_budget_policy("quality_first")
        self.assertEqual(get_budget_status(315, policy), "watch_70")
        self.assertEqual(get_budget_status(360, policy), "reduce_volume_80")
        self.assertEqual(get_budget_status(405, policy), "degrade_90")
        self.assertEqual(get_budget_status(450, policy), "stop_100")
        self.assertEqual(get_budget_status(600, policy), "hard_stop")

    def test_cli_budget_policy_and_estimate_and_status(self):
        for args in (
            ["budget-policy", "quality_first"],
            ["budget-estimate", "quality_first", "--scenario", "baseline_efficient"],
            ["budget-status", "quality_first", "--spent-usd", "410"],
        ):
            proc = subprocess.run(
                [sys.executable, "-m", "zyw_insight.cli", *args],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIsInstance(json.loads(proc.stdout), dict)


if __name__ == "__main__":
    unittest.main()
