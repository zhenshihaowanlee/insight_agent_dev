import unittest

from zyw_insight.openrouter_canary import redact_response_choices
from zyw_insight.schema_validation import SchemaValidationError, validate_json


class CanaryResponseRedactionTests(unittest.TestCase):
    def test_redacts_content_reasoning_and_reasoning_details(self):
        choices = [
            {
                "index": 0,
                "finish_reason": "length",
                "native_finish_reason": "length",
                "message": {
                    "role": "assistant",
                    "content": "full answer",
                    "reasoning": "private reasoning",
                    "reasoning_details": [{"text": "private chain details"}],
                },
            }
        ]
        redacted = redact_response_choices(choices)
        message = redacted[0]["message"]
        self.assertNotIn("content", message)
        self.assertNotIn("reasoning", message)
        self.assertNotIn("reasoning_details", message)
        self.assertTrue(message["content_redacted"])
        self.assertTrue(message["reasoning_redacted"])
        self.assertTrue(message["reasoning_details_redacted"])
        self.assertGreater(message["reasoning_length"], 0)

    def test_schema_rejects_raw_reasoning(self):
        payload = {
            "canary_run_id": "c",
            "created_at": "now",
            "dry_run": False,
            "real_call_requested": True,
            "real_call_executed": True,
            "manual_approval": {"real_call_flag": True, "allow_network_flag": True, "confirm_charge_flag": True, "max_cost_usd": 1, "manual_override": False},
            "provider": "openrouter",
            "internal_model_id": "openrouter/example/model",
            "api_model_slug": "example/model",
            "stage": "literature_analysis",
            "request": {"manual_required": False},
            "response": {"choices": [{"message": {"reasoning": "raw"}}]},
            "usage": {},
            "cost": {"max_cost_usd": 1},
            "ledger_event": {"manual_required": False},
            "runtime_boundary": {"codex_runtime_used": False, "network_request_sent": True, "api_key_logged": False, "body_logged": False, "messages_logged": False},
            "validation": {},
            "notes": [],
        }
        with self.assertRaises(SchemaValidationError):
            validate_json(payload, "openrouter_canary")


if __name__ == "__main__":
    unittest.main()
