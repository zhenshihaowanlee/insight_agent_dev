import unittest
from pathlib import Path

from scripts.validate_codex_metadata import validate_agents, validate_skills


class CodexMetadataTest(unittest.TestCase):
    def test_codex_skill_frontmatter_is_valid(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(validate_skills(root), [])

    def test_codex_agent_toml_is_valid(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(validate_agents(root), [])


if __name__ == "__main__":
    unittest.main()
