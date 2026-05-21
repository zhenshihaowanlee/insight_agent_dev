import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OpenRouterCanaryCliTests(unittest.TestCase):
    def test_cli_canary_dry_run_outputs_json(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "zyw_insight.cli",
                "openrouter-canary",
                "literature_analysis",
                "examples/sample_inputs/sample_paper.md",
                "--internal-model-id",
                "openrouter/example/model-slug",
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

    def test_cli_canary_output_and_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d) / "canary.json"
            ledger = Path(d) / "ledger.jsonl"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "zyw_insight.cli",
                    "openrouter-canary",
                    "literature_analysis",
                    "examples/sample_inputs/vendor_whitepaper.txt",
                    "--internal-model-id",
                    "openrouter/example/model-slug",
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
