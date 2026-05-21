# ZYW Source Discovery Real Metadata Template

Run metadata-only source discovery for candidate technical papers, standards, RFCs, and engineering reports.

Allowed:

- Discovery network to approved metadata providers only.
- Local JSON artifact output.
- CNI discovery triage and watchlist generation.

Not allowed:

- OpenRouter model calls.
- Provider credential access.
- PDF retrieval.
- Full text retrieval.
- Paywall bypass.
- Email or external delivery.

Expected command shape:

```text
PYTHONPATH=src python3 -m zyw_insight.cli discover-sources --query-profile datacenter_networking --provider arxiv --provider openalex --provider semantic_scholar --provider crossref --provider ietf --max-candidates 20 --pretty
```
