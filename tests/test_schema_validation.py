import unittest
from pathlib import Path

from zyw_insight.analyzer import analyze_source
from zyw_insight.ingestion import ingest_file
from zyw_insight.schema_validation import SchemaValidationError, load_schema, validate_json
from zyw_insight.triage import triage_source


ROOT = Path(__file__).resolve().parents[1]


class SchemaValidationTests(unittest.TestCase):
    def test_load_schema_by_name(self):
        schema = load_schema("literature_analysis")
        self.assertEqual(schema["title"], "CNILiteratureAnalysis")

    def test_valid_analysis_passes_minimal_validation(self):
        source = ingest_file(ROOT / "examples/sample_inputs/sample_paper.md")
        analysis = analyze_source(source, triage_source(source))
        self.assertTrue(validate_json(analysis, "literature_analysis"))

    def test_invalid_score_fails(self):
        source = ingest_file(ROOT / "examples/sample_inputs/sample_paper.md")
        analysis = analyze_source(source, triage_source(source))
        analysis["score"]["total_score"] = 101
        with self.assertRaises(SchemaValidationError):
            validate_json(analysis, "literature_analysis")


if __name__ == "__main__":
    unittest.main()
