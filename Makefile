.PHONY: test budget quality runtime-guard codex-metadata install-harness-dry-run

PYTHON ?= python3

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests

budget:
	PYTHONPATH=src $(PYTHON) -m zyw_insight.cli budget --scenario baseline_efficient

quality:
	PYTHONPATH=src $(PYTHON) -m zyw_insight.cli quality-check examples/sample_outputs/literature_analysis.json

runtime-guard:
	PYTHONPATH=src $(PYTHON) -m zyw_insight.cli runtime-guard openclaw/harness/config/openclaw.runtime.openrouter-only.json5

install-harness-dry-run:
	bash scripts/install_openclaw_harness.sh --dry-run

codex-metadata:
	$(PYTHON) scripts/validate_codex_metadata.py
