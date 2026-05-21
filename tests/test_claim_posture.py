import unittest

from zyw_insight.claim_posture import classify_claim_posture, detect_strong_claims, is_guarded_production_phrase


class ClaimPostureTests(unittest.TestCase):
    def test_ready_for_production_is_strong_claim(self):
        posture = classify_claim_posture("ready for production")
        self.assertEqual(posture["posture"], "strong_claim")
        self.assertTrue(posture["requires_revision"])

    def test_not_ready_for_production_is_negative_guardrail(self):
        posture = classify_claim_posture("not ready for production")
        self.assertEqual(posture["posture"], "negative_guardrail")
        self.assertFalse(posture["requires_revision"])

    def test_requires_validation_before_production_use_is_allowed(self):
        posture = classify_claim_posture("requires validation before production use")
        self.assertIn(posture["posture"], {"negative_guardrail", "conditional_claim"})
        self.assertFalse(posture["requires_revision"])

    def test_deploy_immediately_is_detected(self):
        claims = detect_strong_claims("deploy immediately")
        self.assertTrue(claims)

    def test_do_not_recommend_production_deployment_is_guarded(self):
        self.assertTrue(is_guarded_production_phrase("do not recommend production deployment"))
        posture = classify_claim_posture("do not recommend production deployment")
        self.assertFalse(posture["requires_revision"])


if __name__ == "__main__":
    unittest.main()
