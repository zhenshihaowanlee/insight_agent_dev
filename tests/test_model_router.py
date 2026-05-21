import unittest

from zyw_insight.model_router import MODEL_PLACEHOLDERS, choose_model_for_stage, validate_openrouter_model_id


class ModelRouterTests(unittest.TestCase):
    def test_default_models_are_openrouter(self):
        for stage in MODEL_PLACEHOLDERS:
            self.assertTrue(choose_model_for_stage(stage).startswith("openrouter/"))

    def test_rejects_codex_provider(self):
        with self.assertRaises(ValueError):
            validate_openrouter_model_id("openrouter/codex-runtime")
        with self.assertRaises(ValueError):
            validate_openrouter_model_id("codex/local")

    def test_unknown_stage_rejected(self):
        with self.assertRaises(ValueError):
            choose_model_for_stage("unknown")


if __name__ == "__main__":
    unittest.main()
