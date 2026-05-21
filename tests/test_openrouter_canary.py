import os
import unittest
from pathlib import Path
from unittest import mock

from zyw_insight.openrouter_canary import (
    build_canary_payload,
    build_openrouter_api_payload,
    execute_openrouter_canary,
    normalize_internal_model_id,
    validate_canary_flags,
)
from zyw_insight.schema_validation import validate_json


ROOT = Path(__file__).resolve().parents[1]


class OpenRouterCanaryTests(unittest.TestCase):
    def test_normalize_accepts_openrouter(self):
        normalized = normalize_internal_model_id("openrouter/example/model-slug")
        self.assertEqual(normalized["api_model_slug"], "example/model-slug")

    def test_normalize_rejects_non_openrouter(self):
        with self.assertRaises(ValueError):
            normalize_internal_model_id("example/model")

    def test_normalize_rejects_forbidden_terms(self):
        for model_id in ("openrouter/codex-bad", "openrouter/coding-agent-bad", "openrouter/oauth-bad", "openrouter/@openai/codex"):
            with self.assertRaises(ValueError):
                normalize_internal_model_id(model_id)

    def test_build_payload_uses_api_slug(self):
        payload = build_canary_payload("literature_analysis", {"source_id": "s1", "body": "untrusted"}, "openrouter/example/model-slug")
        self.assertEqual(payload["model"], "example/model-slug")
        self.assertNotIn("openrouter/", payload["model"])
        self.assertNotIn("untrusted", str(payload["metadata"]))

    def test_api_payload_excludes_local_metadata(self):
        payload = build_canary_payload("literature_analysis", {"source_id": "s1"}, "openrouter/example/model-slug")
        api_payload = build_openrouter_api_payload(payload)
        self.assertIn("messages", api_payload)
        self.assertNotIn("metadata", api_payload)

    def test_default_canary_is_dry_run(self):
        run = execute_openrouter_canary("literature_analysis", {"source_id": "s1"}, "openrouter/example/model-slug")
        self.assertTrue(run["dry_run"])
        self.assertFalse(run["real_call_executed"])
        self.assertTrue(validate_json(run, "openrouter_canary"))

    def test_dry_run_does_not_require_api_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            result = validate_canary_flags(False, False, False, None)
        self.assertTrue(result["allowed"])
        self.assertFalse(result["api_key_present"])

    def test_real_call_requires_flags_and_key(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(validate_canary_flags(True, False, True, 1.0)["allowed"])
            self.assertFalse(validate_canary_flags(True, True, False, 1.0)["allowed"])
            self.assertFalse(validate_canary_flags(True, True, True, None)["allowed"])
            self.assertFalse(validate_canary_flags(True, True, True, 1.0)["allowed"])

    def test_final_review_requires_manual_override(self):
        with mock.patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-not-real"}, clear=True):
            result = validate_canary_flags(True, True, True, 1.0, manual_override=False, stage="final_review")
        self.assertFalse(result["allowed"])


if __name__ == "__main__":
    unittest.main()
