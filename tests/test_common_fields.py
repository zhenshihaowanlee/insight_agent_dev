import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from zyw_insight.analyzer import analyze_source
from zyw_insight.common_fields import COMMON_FIELD_KEYS
from zyw_insight.critic import critique_analysis
from zyw_insight.ingestion import ingest_file
from zyw_insight.triage import triage_source


ROOT = Path(__file__).resolve().parents[1]


def analyzed_sample(name="sample_paper.md"):
    source = ingest_file(ROOT / f"examples/sample_inputs/{name}")
    return analyze_source(source, triage_source(source))


class CommonFieldTests(unittest.TestCase):
    def test_analyzer_has_common_fields(self):
        analysis = analyzed_sample()
        for key in COMMON_FIELD_KEYS:
            self.assertIn(key, analysis)

    def test_critic_has_common_fields(self):
        analysis = analyzed_sample("vendor_whitepaper.txt")
        critic = critique_analysis(analysis)
        for key in COMMON_FIELD_KEYS:
            self.assertIn(key, critic)
        self.assertEqual(critic["recommended_action"], critic["recommended_action_after"])
        self.assertEqual(critic["score"], critic["score_after"])

    def test_brief_json_source_items_have_common_fields(self):
        with tempfile.TemporaryDirectory() as d:
            input_dir = Path(d) / "inputs"
            input_dir.mkdir()
            analysis = analyzed_sample()
            critic = critique_analysis(analysis)
            (input_dir / "combined.json").write_text(json.dumps({"analysis": analysis, "critic": critic}), encoding="utf-8")
            output = Path(d) / "brief.json"
            subprocess.run(
                [sys.executable, "-m", "zyw_insight.cli", "brief", str(input_dir), "--output", str(output)],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("source_items", payload)
            for key in COMMON_FIELD_KEYS:
                self.assertIn(key, payload["source_items"][0])


if __name__ == "__main__":
    unittest.main()
