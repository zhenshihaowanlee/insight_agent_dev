import unittest

from zyw_insight.quality_gates import evaluate_analysis, gate_status


class QualityGateTests(unittest.TestCase):
    def minimal_analysis(self):
        return {
            "recommended_action": "A",
            "conclusion_strength": "strong",
            "constraints": [],
            "evidence_quality": {"real_deployment": "D", "physical_testbed": "D", "simulation": "D", "baseline": "D"},
            "network_impact_vector": {},
            "security_and_operations": {},
            "degraded_process_counterfactual": {"verdict": "conditional", "conditions": []},
        }

    def test_blocks_strong_conclusion_without_evidence(self):
        issues = evaluate_analysis(self.minimal_analysis())
        self.assertEqual(gate_status(issues), "block")
        self.assertTrue(any(i.rule == "evidence_required" for i in issues))
        self.assertTrue(any(i.rule == "constraints_missing" for i in issues))

    def test_passes_reasonable_stub(self):
        analysis = self.minimal_analysis()
        analysis.update({
            "recommended_action": "C",
            "conclusion_strength": "weak",
            "constraints": [{"name": "BER", "type": "device"}],
            "degraded_process_counterfactual": {"verdict": "unknown", "conditions": []},
            "network_impact_vector": {key: {"impact": "?", "evidence": "unknown", "risk": "unknown"} for key in [
                "Latency", "Jitter/IPDV", "Bandwidth/Capacity", "Reliability", "Security", "Operations", "BER/Error", "Scalability", "Cost/Power"
            ]},
        })
        issues = evaluate_analysis(analysis)
        self.assertNotEqual(gate_status(issues), "block")


if __name__ == "__main__":
    unittest.main()
