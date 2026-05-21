import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliRun72hDryRunTests(unittest.TestCase):
    def test_cli_run_72h_dry_run_outputs_json(self):
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "zyw_insight.cli",
                    "run-72h-dry-run",
                    "examples/sample_inputs",
                    "--output-dir",
                    d,
                    "--environment",
                    "quality_first",
                    "--spent-usd",
                    "50",
                ],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["dry_run"])
            self.assertFalse(payload["runtime_boundary"]["network_request_sent"])

    def test_cli_run_72h_dry_run_output_file(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "pipeline_run.json"
            artifacts = Path(d) / "artifacts"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "zyw_insight.cli",
                    "run-72h-dry-run",
                    "examples/sample_inputs",
                    "--output-dir",
                    str(artifacts),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["dry_run"])


if __name__ == "__main__":
    unittest.main()
