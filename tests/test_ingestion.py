import json
import subprocess
import sys
import unittest
from pathlib import Path

from zyw_insight.ingestion import ingest_file


ROOT = Path(__file__).resolve().parents[1]


class IngestionTests(unittest.TestCase):
    def test_ingest_markdown_extracts_title(self):
        item = ingest_file(ROOT / "examples/sample_inputs/sample_paper.md")
        self.assertEqual(item["title"], "SwiftDC: Tail-Aware RDMA Congestion Control for Datacenter Fabrics")
        self.assertEqual(item["source_type"], "markdown")

    def test_ingest_text_generates_content_hash(self):
        item = ingest_file(ROOT / "examples/sample_inputs/vendor_whitepaper.txt")
        self.assertEqual(item["source_type"], "text")
        self.assertEqual(len(item["content_hash"]), 64)
        self.assertEqual(item["content_hash"], item["hash"])

    def test_body_is_untrusted(self):
        item = ingest_file(ROOT / "examples/sample_inputs/sample_paper.md")
        self.assertIs(item["body_is_untrusted"], True)
        self.assertIn("untrusted", item["rationale"])

    def test_cli_ingest_returns_json(self):
        proc = subprocess.run(
            [sys.executable, "-m", "zyw_insight.cli", "ingest", str(ROOT / "examples/sample_inputs/sample_paper.md")],
            cwd=ROOT,
            env={"PYTHONPATH": "src"},
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["source_type"], "markdown")
        self.assertTrue(payload["body_is_untrusted"])


if __name__ == "__main__":
    unittest.main()
