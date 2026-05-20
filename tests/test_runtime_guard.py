import unittest
from pathlib import Path

from zyw_insight.runtime_guard import check_runtime_config


ROOT = Path(__file__).resolve().parents[1]


class RuntimeGuardTests(unittest.TestCase):
    def test_runtime_config_is_openrouter_only(self):
        result = check_runtime_config(ROOT / "openclaw/harness/config/openclaw.runtime.openrouter-only.json5")
        self.assertTrue(result.ok, result.failures)

    def test_runtime_guard_rejects_codex_provider(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.json5"
            bad.write_text('{ model: "codex/local" }', encoding="utf-8")
            result = check_runtime_config(bad)
            self.assertFalse(result.ok)
            self.assertTrue(any("forbidden" in item for item in result.failures))


if __name__ == "__main__":
    unittest.main()
