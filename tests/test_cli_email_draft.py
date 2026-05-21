import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from zyw_insight.pipeline import run_72h_dry_run_pipeline


ROOT = Path(__file__).resolve().parents[1]


class CliEmailDraftTests(unittest.TestCase):
    def test_cli_email_draft_outputs_json(self):
        with tempfile.TemporaryDirectory() as d:
            run = run_72h_dry_run_pipeline("examples/sample_inputs", output_dir=Path(d) / "run")
            proc = subprocess.run(
                [sys.executable, "-m", "zyw_insight.cli", "email-draft", run["artifacts"]["output_dir"], "--output-dir", str(Path(d) / "draft")],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["draft_only"])

    def test_cli_email_draft_output_file(self):
        with tempfile.TemporaryDirectory() as d:
            run = run_72h_dry_run_pipeline("examples/sample_inputs", output_dir=Path(d) / "run")
            output = Path(d) / "manifest.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "zyw_insight.cli",
                    "email-draft",
                    run["artifacts"]["output_dir"],
                    "--output-dir",
                    str(Path(d) / "draft"),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["draft_only"])


if __name__ == "__main__":
    unittest.main()
