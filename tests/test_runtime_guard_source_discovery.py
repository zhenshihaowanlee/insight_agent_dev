import unittest
from pathlib import Path

from zyw_insight.runtime_guard import check_runtime_config


ROOT = Path(__file__).resolve().parents[1]


class RuntimeGuardSourceDiscoveryTests(unittest.TestCase):
    def test_runtime_guard_source_discovery_passes(self):
        result = check_runtime_config(ROOT / "openclaw/harness/config/openclaw.runtime.openrouter-only.json5")
        self.assertTrue(result.ok, result.failures)


if __name__ == "__main__":
    unittest.main()
