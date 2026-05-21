import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from zyw_insight.email_draft import build_email_draft
from zyw_insight.pipeline import run_72h_dry_run_pipeline


ROOT = Path(__file__).resolve().parents[1]


class CliPreSendReviewTests(unittest.TestCase):
    def test_cli_pre_send_review_outputs_json(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = run_72h_dry_run_pipeline("examples/sample_inputs", output_dir=root / "run")
            draft = build_email_draft(run["artifacts"]["output_dir"], output_dir=root / "draft")
            proc = subprocess.run(
                [sys.executable, "-m", "zyw_insight.cli", "pre-send-review", str(Path(draft["body"]["markdown_path"]).parent)],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=True,
            )
            payload = json.loads(proc.stdout)
            self.assertTrue(payload["dry_run"])

    def test_cli_pre_send_review_output_file(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = run_72h_dry_run_pipeline("examples/sample_inputs", output_dir=root / "run")
            draft = build_email_draft(run["artifacts"]["output_dir"], output_dir=root / "draft")
            output = root / "review.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "zyw_insight.cli",
                    "pre-send-review",
                    str(Path(draft["body"]["markdown_path"]).parent),
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
