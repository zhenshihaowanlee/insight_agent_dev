import json
import unittest

from zyw_insight.full_paper_canary import CNI_REQUIRED_SECTIONS, _cni_sections_present
from zyw_insight.openrouter_canary import _extract_json_object, build_one_shot_fulltext_messages


class FullPaperSchemaContractTests(unittest.TestCase):
    def test_parser_extracts_pure_json(self):
        payload = {"basic_info": {}, "core_idea": "x"}
        self.assertEqual(_extract_json_object(json.dumps(payload)), payload)

    def test_parser_extracts_fenced_json(self):
        payload = {"basic_info": {}, "core_idea": "x"}
        self.assertEqual(_extract_json_object("```json\n" + json.dumps(payload) + "\n```"), payload)

    def test_parser_extracts_json_with_small_surrounding_text(self):
        payload = {"basic_info": {}, "core_idea": "x"}
        self.assertEqual(_extract_json_object("Here:\n" + json.dumps(payload) + "\nDone"), payload)

    def test_missing_required_cni_keys_is_detected(self):
        self.assertLess(len(_cni_sections_present({"basic_info": {}})), len(CNI_REQUIRED_SECTIONS))

    def test_schema_valid_section_count_is_20(self):
        payload = {key: {} for key in CNI_REQUIRED_SECTIONS}
        self.assertEqual(len(_cni_sections_present(payload)), 20)

    def test_prompt_contains_score_contract(self):
        prompt = "\n".join(item["content"] for item in build_one_shot_fulltext_messages("MegaScale-Infer", "paper text"))
        self.assertIn("score.total_score MUST be a bare JSON number", prompt)
        for key in CNI_REQUIRED_SECTIONS:
            self.assertIn(key, prompt)


if __name__ == "__main__":
    unittest.main()
