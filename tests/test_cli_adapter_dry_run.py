import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliAdapterDryRunTests(unittest.TestCase):
    def test_cli_adapter_dry_run_outputs_json(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "zyw_insight.cli",
                "adapter-dry-run",
                "literature_analysis",
                "examples/sample_inputs/sample_paper.md",
                "--environment",
                "quality_first",
                "--spent-usd",
                "50",
                "--source-tier",
                "A",
                "--deep-read-priority",
                "High",
            ],
            cwd=ROOT,
            env={"PYTHONPATH": "src"},
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["dry_run"])

    def test_cli_adapter_output_and_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "adapter.json"
            ledger = Path(d) / "ledger.jsonl"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "zyw_insight.cli",
                    "adapter-dry-run",
                    "brief_synthesis",
                    "examples/sample_brief_inputs",
                    "--write-ledger",
                    "--ledger-path",
                    str(ledger),
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
            raw = ledger.read_text(encoding="utf-8")
            self.assertNotIn("messages", raw)
            self.assertNotIn("body", raw)


if __name__ == "__main__":
    unittest.main()
