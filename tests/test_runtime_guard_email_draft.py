import unittest

from zyw_insight.runtime_guard import check_runtime_config


class RuntimeGuardEmailDraftTests(unittest.TestCase):
    def test_runtime_guard_email_draft_checks_pass(self):
        result = check_runtime_config("openclaw/harness/config/openclaw.runtime.openrouter-only.json5")
        self.assertTrue(result.ok, result.failures)


if __name__ == "__main__":
    unittest.main()
