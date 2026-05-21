import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliPipelineCanaryTests(unittest.TestCase):
    def test_cli_pipeline_canary_outputs_json(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "zyw_insight.cli",
                "pipeline-canary",
                "examples/sample_inputs/sample_paper.md",
                "--internal-model-id",
                "openrouter/example/model-slug",
                "--max-cost-usd",
                "5",
            ],
            cwd=ROOT,
            env={"PYTHONPATH": "src"},
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["real_call_executed"])

    def test_cli_pipeline_canary_output_file(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "manifest.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "zyw_insight.cli",
                    "pipeline-canary",
                    "examples/sample_inputs/sample_paper.md",
                    "--internal-model-id",
                    "openrouter/example/model-slug",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(proc.stdout, "")
            self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["dry_run"])


if __name__ == "__main__":
    unittest.main()
