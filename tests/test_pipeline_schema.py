import unittest
from datetime import datetime, timezone

from zyw_insight.schema_validation import validate_json


class PipelineSchemaTests(unittest.TestCase):
    def test_pipeline_run_minimal_schema_valid(self):
        run = {
            "run_id": "pipe-test",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": True,
            "trigger": "manual",
            "input": {"input_dir": "examples/sample_inputs", "document_count": 0, "max_documents": 0},
            "environment": "quality_first",
            "quality_priority": "high",
            "budget_context": {"spent_usd": 0, "budget_status": "ok", "policy_id": "budget.quality_first"},
            "stages": {},
            "artifacts": {"brief_json": "brief/brief.json", "brief_markdown": "brief/brief.md"},
            "draft_delivery": {"mode": "draft_only", "requires_human_approval": True, "external_delivery_sent": False},
            "runtime_boundary": {
                "openrouter_only": True,
                "codex_runtime_used": False,
                "real_openrouter_call_executed": False,
                "canary_real_call_executed": False,
                "network_request_sent": False,
                "api_key_read": False,
                "email_sent": False,
                "webhook_sent": False,
            },
            "guardrail_results": [],
            "validation": {},
            "notes": [],
        }
        self.assertTrue(validate_json(run, "pipeline_run"))

    def test_draft_artifact_schema_valid(self):
        artifact = {
            "artifact_id": "art-test",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "artifact_type": "markdown_brief",
            "path": "brief/brief.md",
            "draft_only": True,
            "requires_human_approval": True,
            "external_delivery_sent": False,
            "source_run_id": "pipe-test",
            "redaction": {"body_logged": False},
            "notes": [],
        }
        self.assertTrue(validate_json(artifact, "draft_artifact"))


if __name__ == "__main__":
    unittest.main()
