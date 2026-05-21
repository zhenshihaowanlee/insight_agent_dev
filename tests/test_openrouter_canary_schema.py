import unittest

from zyw_insight.openrouter_canary import execute_openrouter_canary
from zyw_insight.schema_validation import validate_json


class OpenRouterCanarySchemaTests(unittest.TestCase):
    def test_canary_schema_valid(self):
        run = execute_openrouter_canary("literature_analysis", {"source_id": "s1"}, "openrouter/example/model-slug")
        self.assertTrue(validate_json(run, "openrouter_canary"))


if __name__ == "__main__":
    unittest.main()
