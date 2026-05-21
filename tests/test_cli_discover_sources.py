import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliDiscoverSourcesTests(unittest.TestCase):
    def test_cli_discover_sources_dry_run_json(self):
        proc = subprocess.run(
            [sys.executable, "-m", "zyw_insight.cli", "discover-sources", "--dry-run", "--pretty"],
            cwd=ROOT,
            env={"PYTHONPATH": "src"},
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["dry_run"])
        self.assertFalse(payload["runtime_boundary"]["model_network_used"])


if __name__ == "__main__":
    unittest.main()
