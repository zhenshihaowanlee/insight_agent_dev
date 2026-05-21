import json
import unittest
from unittest import mock

from zyw_insight.source_discovery import query_openalex
from zyw_insight.source_registry import load_source_discovery_config


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"results": [{"id": "https://openalex.org/W1", "display_name": "RDMA datacenter fabric", "authorships": [], "publication_year": 2026, "abstract_inverted_index": {"rdma": [0], "datacenter": [1]}}]}).encode()


class RealDiscoveryProviderContractTests(unittest.TestCase):
    def test_openalex_query_uses_metadata_endpoint(self):
        config = load_source_discovery_config()
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse()) as patched:
            results = query_openalex("datacenter_networking", 1, config)
        self.assertEqual(results[0]["source_provider"], "openalex")
        request = patched.call_args.args[0]
        self.assertIn("api.openalex.org/works", request.full_url)
        self.assertTrue(results[0]["body_is_untrusted"])


if __name__ == "__main__":
    unittest.main()
