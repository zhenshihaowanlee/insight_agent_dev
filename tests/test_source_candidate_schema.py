import unittest

from zyw_insight.source_discovery import _candidate
from zyw_insight.schema_validation import validate_json


class SourceCandidateSchemaTests(unittest.TestCase):
    def test_candidate_schema_valid_and_untrusted(self):
        candidate = _candidate("arxiv", "1234", "RDMA congestion control", "baseline experiment p99 datacenter", ["A"], "2026", None, "arXiv", "https://arxiv.org/abs/1234", "https://arxiv.org/pdf/1234")
        self.assertTrue(candidate["body_is_untrusted"])
        self.assertTrue(validate_json(candidate, "source_candidate"))


if __name__ == "__main__":
    unittest.main()
