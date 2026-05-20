# Task 01 — Repository scaffold validation

Goal: verify this repo is installable and tests run.

Steps for Codex:

1. Inspect `pyproject.toml`, `src/zyw_insight`, and `tests`.
2. Run `python -m pip install -e .`.
3. Run `make test`.
4. Fix only minimal issues.
5. Report changed files and test results.

Acceptance:

- `make test` passes.
- No secrets added.
