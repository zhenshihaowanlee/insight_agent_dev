import unittest

from zyw_insight.full_paper_canary import CNI_REQUIRED_SECTIONS, _cni_sections_present


class FullPaperAnalysisSectionTests(unittest.TestCase):
    def test_all_20_cni_sections_are_checked(self):
        payload = {key: {} for key in CNI_REQUIRED_SECTIONS}
        present = _cni_sections_present(payload)
        self.assertEqual(len(present), 20)
        self.assertEqual(set(present), set(CNI_REQUIRED_SECTIONS))


if __name__ == "__main__":
    unittest.main()
