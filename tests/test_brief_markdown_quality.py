import tempfile
import unittest
from pathlib import Path

from zyw_insight.pipeline import run_72h_dry_run_pipeline


class BriefMarkdownQualityTests(unittest.TestCase):
    def _rendered_markdown(self) -> str:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        run = run_72h_dry_run_pipeline("examples/sample_inputs", output_dir=directory.name, spent_usd=50)
        return Path(run["artifacts"]["brief_markdown"]).read_text(encoding="utf-8")

    def test_markdown_has_no_developer_status_top_conclusion(self):
        text = self._rendered_markdown()
        self.assertNotIn("Processed 5 item(s)", text)

    def test_markdown_has_no_item_placeholder_or_field_name_placeholders(self):
        text = self._rendered_markdown()
        self.assertNotIn("- item", text)
        self.assertNotIn("evidence_grade_counts", text)
        self.assertNotIn("downgraded_count", text)
        self.assertNotIn("vendor_or_marketing_risk_count", text)
        self.assertNotIn("strong_conclusion_allowed", text)

    def test_markdown_has_no_python_dict_direct_output(self):
        text = self._rendered_markdown()
        self.assertNotIn("{'dominant_impact'", text)
        self.assertNotIn("'impact_counts'", text)

    def test_key_sections_are_markdown_tables(self):
        text = self._rendered_markdown()
        self.assertIn("| Direction | Signal Strength | Evidence Count | Recommended Action | Constraint Risks | Why Not Stronger |", text)
        self.assertIn("| Metric | Dominant Impact | Evidence Count | Main Risks | Required Validation |", text)
        self.assertIn("| Technology / Source | Action | Rationale | Evidence Basis | Constraint Risk | Next Step | Traceability |", text)

    def test_low_confidence_all_c_not_ready_for_direct_poc(self):
        text = self._rendered_markdown()
        self.assertIn("Overall confidence: low", text)
        self.assertIn("Ready for PoC: false", text)

    def test_draft_and_human_approval_remain(self):
        text = self._rendered_markdown()
        self.assertIn("DRAFT ONLY", text)
        self.assertIn("Human Approval Required", text)


if __name__ == "__main__":
    unittest.main()
