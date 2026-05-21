import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from zyw_insight.source_discovery import discover_sources


ROOT = Path(__file__).resolve().parents[1]


class CliDiscoveryTriageTests(unittest.TestCase):
    def test_cli_discovery_triage_outputs_watchlist(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "discovery.json"
            path.write_text(json.dumps(discover_sources(dry_run=True)), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "zyw_insight.cli", "discovery-triage", str(path), "--pretty"],
                cwd=ROOT,
                env={"PYTHONPATH": "src"},
                text=True,
                capture_output=True,
                check=True,
            )
        payload = json.loads(proc.stdout)
        self.assertIn("watchlist", payload)
        self.assertFalse(payload["strong_conclusion_allowed"])


if __name__ == "__main__":
    unittest.main()
