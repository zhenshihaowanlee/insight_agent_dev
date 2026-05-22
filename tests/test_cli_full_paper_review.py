import json
import tempfile
import unittest
from pathlib import Path

from zyw_insight.cli import main
from tests.test_full_paper_canonicalizer import sample_analysis


class CliFullPaperReviewTests(unittest.TestCase):
    def test_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            analysis_path = root / "analysis.json"
            audit_path = root / "run.json"
            out = root / "review"
            analysis_path.write_text(json.dumps(sample_analysis()), encoding="utf-8")
            audit_path.write_text(json.dumps({"actual_input_tokens": 10000, "normalization_applied": True}), encoding="utf-8")
            code = main(["full-paper-review", str(analysis_path), "--run-audit", str(audit_path), "--output-dir", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue((out / "canonical_full_paper_analysis.json").exists())
            self.assertTrue((out / "canonical_full_paper_analysis.md").exists())
            self.assertTrue((out / ".full_paper_consistency_report.json").exists())
            self.assertTrue((out / ".full_paper_consistency_report.md").exists())


if __name__ == "__main__":
    unittest.main()
