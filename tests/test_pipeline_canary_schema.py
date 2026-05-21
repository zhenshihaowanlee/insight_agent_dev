import unittest

from zyw_insight.schema_validation import SchemaValidationError, validate_json


def _base_canary():
    return {
        "pipeline_canary_id": "pc",
        "created_at": "now",
        "dry_run": True,
        "real_call_requested": False,
        "real_call_executed": False,
        "manual_approval": {
            "real_call_flag": False,
            "allow_network_flag": False,
            "confirm_charge_flag": False,
            "max_cost_usd": 5,
            "max_documents": 1,
            "allowed_real_stages": ["literature_analysis"],
            "manual_override": False,
        },
        "input": {"input_dir_or_file": "x", "selected_documents": [], "skipped_documents": [], "max_documents": 1},
        "environment": "quality_first",
        "quality_priority": "high",
        "stages": {},
        "real_stage_canaries": [],
        "artifacts": {},
        "runtime_boundary": {
            "openrouter_only": True,
            "codex_runtime_used": False,
            "cron_triggered_real_call": False,
            "network_request_sent": False,
            "api_key_logged": False,
            "body_logged": False,
            "messages_logged": False,
            "reasoning_logged": False,
            "email_sent": False,
            "webhook_sent": False,
        },
        "budget": {"max_cost_usd": 5, "estimated_cost_usd": 0, "actual_cost_usd": None, "audit_cost_usd": 0, "budget_status": "ok"},
        "validation": {"schema_valid": True},
        "notes": [],
    }


class PipelineCanarySchemaTests(unittest.TestCase):
    def test_base_schema_valid(self):
        self.assertTrue(validate_json(_base_canary(), "pipeline_canary"))

    def test_dry_run_cannot_have_real_execution(self):
        payload = _base_canary()
        payload["real_call_executed"] = True
        with self.assertRaises(SchemaValidationError):
            validate_json(payload, "pipeline_canary")

    def test_forbidden_stage_schema_rejected(self):
        for stage in ("final_review", "brief_synthesis"):
            payload = _base_canary()
            payload["manual_approval"]["allowed_real_stages"] = [stage]
            with self.assertRaises(SchemaValidationError):
                validate_json(payload, "pipeline_canary")


if __name__ == "__main__":
    unittest.main()
