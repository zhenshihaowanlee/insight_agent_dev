import unittest

from zyw_insight.openrouter_canary import build_canary_payload, build_one_shot_fulltext_messages


class OneShotFulltextPromptTests(unittest.TestCase):
    def test_one_shot_prompt_includes_selected_text(self):
        selected_text = "UNIQUE_FULLTEXT_SENTINEL MegaScale-Infer paper body"
        messages = build_one_shot_fulltext_messages("MegaScale-Infer", selected_text)
        joined = "\n".join(item["content"] for item in messages)
        self.assertIn("UNIQUE_FULLTEXT_SENTINEL", joined)
        self.assertIn("full_text_limited_analysis", joined)
        for key in ("basic_info", "network_impact_vector", "follow_up_validation_experiments", "cni_content_patch"):
            self.assertIn(key, joined)
        self.assertIn("Return JSON only", joined)

    def test_default_canary_payload_still_redacts_body(self):
        payload = build_canary_payload("literature_analysis", {"source_id": "s1", "body": "UNIQUE_FULLTEXT_SENTINEL"}, "openrouter/qwen/qwen3.5-397b-a17b")
        joined = "\n".join(item["content"] for item in payload["messages"])
        self.assertNotIn("UNIQUE_FULLTEXT_SENTINEL", joined)


if __name__ == "__main__":
    unittest.main()
