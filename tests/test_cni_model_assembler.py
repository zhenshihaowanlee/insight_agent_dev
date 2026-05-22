import unittest

from zyw_insight.analyzer import analyze_source
from zyw_insight.cni_model_assembler import assemble_literature_analysis_from_model_patch
from zyw_insight.schema_validation import validate_json
from zyw_insight.triage import triage_source


class CNIModelAssemblerTests(unittest.TestCase):
    def base(self):
        source = {
            "source_id": "s1",
            "id": "s1",
            "title": "MegaScale-Infer",
            "source_type": "paper",
            "body": "SIGCOMM datacenter GPU communication evaluation baseline p95 p99 implementation telemetry.",
            "body_is_untrusted": True,
        }
        return analyze_source(source, triage_source(source))

    def test_assembles_schema_valid_analysis_from_content_patch(self):
        patch = {
            "cni_content_patch": {
                "one_sentence_conclusion": "MegaScale-Infer is relevant but requires independent validation.",
                "core_idea": "Disaggregate expert parallelism for MoE inference serving.",
                "recommended_action": "B",
                "score": {"total_score": 72.0, "score_explanation": "Promising but bounded by evidence gaps."},
                "network_impact_vector": {
                    "latency": {"impact": "+", "evidence": "reports latency-oriented serving design", "risk": "tail behavior needs reproduction"}
                },
            }
        }
        assembled = assemble_literature_analysis_from_model_patch(self.base(), patch)
        self.assertTrue(validate_json(assembled, "literature_analysis"))
        self.assertEqual(assembled["recommended_action"], "B")
        self.assertEqual(assembled["score"]["total_score"], 72.0)
        self.assertTrue(assembled["model_patch_assembly"]["assembly_applied"])

    def test_rejects_invalid_patch_values_but_keeps_schema_valid_base(self):
        patch = {"cni_content_patch": {"recommended_action": "deploy", "score": {"total_score": "high"}}}
        assembled = assemble_literature_analysis_from_model_patch(self.base(), patch)
        self.assertTrue(validate_json(assembled, "literature_analysis"))
        self.assertNotEqual(assembled["recommended_action"], "deploy")


if __name__ == "__main__":
    unittest.main()
