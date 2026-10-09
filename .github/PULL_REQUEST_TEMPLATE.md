## Summary

<!-- What changed and why. Link the docs/PLAN.md task IDs (e.g. C2, P4). -->

## Test plan

- [ ] `uv run pytest` (coverage ≥ 80%), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`
- [ ] `npm --prefix web run lint && npm --prefix web run typecheck && npm --prefix web run coverage`
- [ ] No live API calls added outside the budget guard; no secrets or `.env` committed
