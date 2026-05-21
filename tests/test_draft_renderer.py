import unittest

from zyw_insight.brief import synthesize_brief
from zyw_insight.draft_renderer import render_brief_markdown


class DraftRendererTests(unittest.TestCase):
    def test_render_brief_markdown_is_draft_and_redacted(self):
        brief = synthesize_brief([], window_hours=72)
        text = render_brief_markdown(brief)
        self.assertIn("DRAFT ONLY", text)
        self.assertIn("Human Approval Required", text)
        self.assertIn("External Delivery Sent: false", text)
        for forbidden in ("API key", "token", "secret", "Authorization", "env"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
