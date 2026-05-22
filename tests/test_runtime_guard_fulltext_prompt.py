import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RuntimeGuardFulltextPromptTests(unittest.TestCase):
    def test_runtime_guard_still_passes_with_manual_fulltext_prompt_support(self):
        proc = subprocess.run(
            [sys.executable, "-m", "zyw_insight.cli", "runtime-guard", "openclaw/harness/config/openclaw.runtime.openrouter-only.json5"],
            cwd=ROOT,
            env={"PYTHONPATH": "src"},
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn('"ok": true', proc.stdout)


if __name__ == "__main__":
    unittest.main()
