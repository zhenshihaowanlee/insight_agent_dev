import unittest
from datetime import datetime, timezone

from zyw_insight.schema_validation import validate_json


class HumanApprovalSchemaTests(unittest.TestCase):
    def test_human_approval_defaults_pending(self):
        payload = {
            "approval_id": "approval-test",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_email_draft_id": "email-test",
            "approval_required": True,
            "approved": False,
            "reviewer": None,
            "checklist": {
                "content_quality_reviewed": False,
                "no_strong_claim_without_evidence": False,
                "vendor_claims_marked": False,
                "budget_context_reviewed": False,
                "draft_only_confirmed": False,
                "no_api_key_or_secret": False,
                "no_external_delivery": False,
                "recipients_reviewed": False,
                "attachments_reviewed": False,
            },
            "approval_decision": "pending",
            "comments": "",
        }
        self.assertTrue(validate_json(payload, "human_approval"))


if __name__ == "__main__":
    unittest.main()
