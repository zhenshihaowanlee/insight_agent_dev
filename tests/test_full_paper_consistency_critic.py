import unittest

from tests.test_full_paper_canonicalizer import sample_analysis
from zyw_insight.full_paper_canonicalizer import canonicalize_full_paper_analysis
from zyw_insight.full_paper_consistency_critic import build_consistency_report, render_canonical_markdown


class FullPaperConsistencyCriticTests(unittest.TestCase):
    def test_report_blocks_three_paper_when_consistency_issues_remain(self):
        canonical = canonicalize_full_paper_analysis(sample_analysis(), {"actual_input_tokens": 10000, "normalization_applied": True})
        report = build_consistency_report(canonical)
        self.assertFalse(report["ready_for_three_paper_cross_validation"])
        self.assertTrue(report["hard_rule_violations"])
        md = render_canonical_markdown(canonical, report)
        self.assertIn("Three-Paper Cross-Validation Readiness", md)
        self.assertIn("AI cluster networking", md)


if __name__ == "__main__":
    unittest.main()
