import unittest

from zyw_insight.runtime_guard import check_runtime_config


class RuntimeGuardCronDryRunTests(unittest.TestCase):
    def test_runtime_guard_checks_cron_dry_run(self):
        result = check_runtime_config("openclaw/harness/config/openclaw.runtime.openrouter-only.json5")
        self.assertTrue(result.ok, result.failures)


if __name__ == "__main__":
    unittest.main()
