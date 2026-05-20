PYTHON ?= python3
PYTHONPATH_DIR ?= src

.PHONY: test budget quality runtime-guard codex-metadata install-harness-dry-run

test:
	PYTHONPATH=$(PYTHONPATH_DIR) $(PYTHON) -m unittest discover -s tests

budget:
	PYTHONPATH=$(PYTHONPATH_DIR) $(PYTHON) -m zyw_insight.cli budget --scenario baseline_efficient

quality:
	PYTHONPATH=$(PYTHONPATH_DIR) $(PYTHON) -m zyw_insight.cli quality-check examples/sample_outputs/literature_analysis.json

runtime-guard:
	PYTHONPATH=$(PYTHONPATH_DIR) $(PYTHON) -m zyw_insight.cli runtime-guard openclaw/harness/config/openclaw.runtime.openrouter-only.json5

install-harness-dry-run:
	bash scripts/install_openclaw_harness.sh --dry-run

codex-metadata:
	$(PYTHON) scripts/validate_codex_metadata.py
