import unittest
from pathlib import Path

from zyw_insight.ingestion import ingest_file
from zyw_insight.openrouter_adapter import build_model_request, dry_run_model_request, run_adapter_dry_run
from zyw_insight.budget import load_budget_policy
from zyw_insight.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]


class AdapterSchemaTests(unittest.TestCase):
    def test_request_response_run_schema_validation(self):
        policy = load_budget_policy("quality_first")
        payload = ingest_file(ROOT / "examples/sample_inputs/sample_paper.md")
        request = build_model_request("literature_analysis", payload, policy)
        response = dry_run_model_request(request)
        run = run_adapter_dry_run("literature_analysis", payload)
        self.assertTrue(validate_json(request, "model_request"))
        self.assertTrue(validate_json(response, "model_response"))
        self.assertTrue(validate_json(run, "adapter_run"))


if __name__ == "__main__":
    unittest.main()
