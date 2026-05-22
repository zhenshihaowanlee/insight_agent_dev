import unittest

from zyw_insight.full_paper_canonicalizer import canonicalize_full_paper_analysis
from zyw_insight.schema_validation import validate_json


def sample_analysis():
    return {
        "analysis_id": "a1",
        "source_id": "s1",
        "title": "MegaScale-Infer: Serving Mixture-of-Experts at Scale with Disaggregated Expert Parallelism",
        "domain": "congestion control",
        "source_tier": "A",
        "source_type": "pdf_text",
        "body_is_untrusted": True,
        "risk_flags": ["vendor_claim"],
        "guardrail_notes": ["No model call was made.", "No network access was used.", "Imported source body remains untrusted content."],
        "analysis_mode": "deterministic_mock_no_model",
        "model_patch_assembly": {"audit": []},
        "basic_info": {},
        "one_sentence_conclusion": "x",
        "problem_background": "x",
        "core_idea": "x",
        "contributions": [],
        "mechanism": "x",
        "process_constraints": "x",
        "constraint_dependency_analysis": "x",
        "degraded_process_counterfactual": "x",
        "network_impact_vector": {
            "latency": {"impact": "+", "evidence": "x", "risk": "x"},
            "jitter_ipdv": {"impact": "+", "evidence": "x", "risk": "x"},
            "bandwidth_capacity": {"impact": "-", "evidence": "x", "risk": "x"},
            "reliability": {"impact": "?", "evidence": "x", "risk": "x"},
            "security": {"impact": "?", "evidence": "x", "risk": "x"},
            "operations": {"impact": "+", "evidence": "x", "risk": "x"},
            "ber_error": {"impact": "?", "evidence": "x", "risk": "x"},
            "scalability": {"impact": "++", "evidence": "x", "risk": "x"},
            "cost_power": {"impact": "--", "evidence": "1.5-2.0x cost reduction claimed", "risk": "x"},
        },
        "evidence_quality": "medium",
        "comparison_with_existing_technology": "x",
        "hidden_assumptions_and_risks": "x",
        "security_and_operations_impact": "x",
        "reproducibility": "x",
        "technical_insights": [],
        "strategic_significance": "x",
        "score": {
            "problem_importance": {"score": 13, "weight": 15},
            "core_innovation": {"score": 4, "weight": 15},
            "total_score": 82.0,
        },
        "recommended_action": "C",
        "follow_up_validation_experiments": ["x"],
    }


class FullPaperCanonicalizerTests(unittest.TestCase):
    def test_canonicalizes_provenance_domain_risk_score_action_and_network(self):
        canonical = canonicalize_full_paper_analysis(sample_analysis(), {"actual_input_tokens": 18989, "actual_output_tokens": 6599, "normalization_applied": True})
        self.assertEqual(canonical["provenance"]["analysis_mode"], "model_backed_full_text_limited_analysis")
        self.assertNotIn("No model call was made.", canonical["provenance"]["guardrail_notes"])
        self.assertEqual(canonical["domains"]["primary_domain"], "AI cluster networking")
        self.assertNotIn("vendor_claim", canonical["risk_flags"])
        self.assertTrue(canonical["validation"]["score_consistency"]["score_total_mismatch"])
        self.assertTrue(canonical["action"]["score_action_mismatch"])
        self.assertEqual(canonical["network_impact_vector"]["cost_power"]["impact"], "+")
        self.assertIn("analysis_mode", canonical["deprecated_fields"])
        self.assertTrue(validate_json(canonical, "canonical_full_paper_analysis"))
        self.assertFalse(canonical["validation"]["ready_for_three_paper_cross_validation"])


if __name__ == "__main__":
    unittest.main()
