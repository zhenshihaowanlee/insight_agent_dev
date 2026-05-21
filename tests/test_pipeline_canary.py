import tempfile
import unittest
from pathlib import Path

from zyw_insight.pipeline_canary import build_stage_canary_plan, run_small_pipeline_canary, select_canary_documents
from zyw_insight.schema_validation import validate_json


class PipelineCanaryTests(unittest.TestCase):
    def test_pipeline_canary_dry_run_schema_valid(self):
        with tempfile.TemporaryDirectory() as d:
            canary = run_small_pipeline_canary(
                "examples/sample_inputs/sample_paper.md",
                output_dir=d,
                internal_model_id="openrouter/example/model-slug",
                max_cost_usd=5,
            )
            self.assertTrue(validate_json(canary, "pipeline_canary"))
            self.assertTrue(canary["dry_run"])
            self.assertFalse(canary["real_call_executed"])
            self.assertEqual(canary["manual_approval"]["max_documents"], 1)
            self.assertEqual(canary["manual_approval"]["allowed_real_stages"], ["literature_analysis"])
            self.assertTrue(Path(canary["artifacts"]["deterministic_brief_json"]).exists())
            self.assertTrue(Path(canary["artifacts"]["deterministic_brief_md"]).exists())
            self.assertTrue(canary["artifacts"]["redacted_canary_runs"])

    def test_max_documents_limit(self):
        with self.assertRaises(ValueError):
            run_small_pipeline_canary("examples/sample_inputs", max_documents=3)

    def test_max_documents_over_two_allowed_with_manual_override_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            canary = run_small_pipeline_canary("examples/sample_inputs", output_dir=d, max_documents=3, manual_override=True)
            self.assertLessEqual(len(canary["input"]["selected_documents"]), 3)

    def test_forbidden_stages_rejected(self):
        docs = select_canary_documents("examples/sample_inputs/sample_paper.md")
        with self.assertRaises(ValueError):
            build_stage_canary_plan(docs, ["final_review"])
        with self.assertRaises(ValueError):
            build_stage_canary_plan(docs, ["brief_synthesis"])
        with self.assertRaises(ValueError):
            build_stage_canary_plan(docs, ["constraint_critic"])


if __name__ == "__main__":
    unittest.main()
