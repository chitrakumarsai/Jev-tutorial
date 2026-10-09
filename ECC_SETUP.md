# ECC Setup Runbook — Jev-tutorial

**How to use:** open Claude Code in this folder and say:

> Read ECC_SETUP.md and execute it phase by phase. Stop at each ⏸ checkpoint for my confirmation.

Claude: follow the phases in order. Do not skip a ⏸ checkpoint. Use `uv` for everything Python.
Day-to-day rules live in [CLAUDE.md](CLAUDE.md) — keep it updated as you go.

---

## Phase 0 — Understand the project

1. Ask me what Jev is, who it's for, and the first 2–3 things it must do. Ask only what you can't infer.
2. Run `/prp-prd` with my answers to produce `docs/PRD.md` (problem, users, scope, non-goals, success criteria).
3. Replace the `_TODO_` line under **Project** in `CLAUDE.md` with a one-line summary.

⏸ Show me the PRD summary and wait.

## Phase 1 — Let ECC inspect the repo

1. Run `/project-init` (dry-run) and show which ECC rules, skills and agents it recommends for this stack.
2. Confirm `~/.claude/rules/ecc/common/` and `~/.claude/rules/ecc/python/` exist (they're global — do **not** copy them into the repo).
3. If the PRD implies a web API, note that `~/.claude/rules/ecc/python/fastapi.md` and the `fastapi-reviewer` agent apply.

⏸ Summarize the recommendations and wait.

## Phase 2 — Plan the scaffold

Delegate to the **planner** agent (and **architect** if the PRD has more than one component) to produce `docs/PLAN.md`:
- package layout under `src/jev/`, test layout under `tests/`
- dependencies (use the `search-first` skill — prefer maintained PyPI packages over hand-rolled code)
- phased task list for the first milestone

⏸ Show me the plan and wait.

## Phase 3 — Scaffold the Python project

1. `uv init --package --name jev --python 3.11` (keep the existing `.venv/` and `.gitignore`).
2. Dev deps: `uv add --dev pytest pytest-cov ruff mypy pre-commit`.
3. In `pyproject.toml` configure:
   - `[tool.ruff]` line-length 100, target `py311`; lint rules `E,F,I,B,UP,SIM,S,N`
   - `[tool.mypy]` `strict = true`, `files = ["src"]`
   - `[tool.pytest.ini_options]` `testpaths = ["tests"]`, `addopts = "--cov=jev --cov-report=term-missing --cov-fail-under=80"`
4. Create `src/jev/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py` (one passing test), `.env.example`, and a short `README.md` (what it is + the commands from `CLAUDE.md`).
5. Verify: `uv run pytest`, `uv run ruff check .`, `uv run mypy src` all pass.

## Phase 4 — Project-level Claude/ECC config

Create `.claude/settings.json` (project-scoped, committed) with:
- **permissions.allow**: `Bash(uv run pytest:*)`, `Bash(uv run ruff:*)`, `Bash(uv run mypy:*)`, `Bash(uv sync:*)`, `Bash(uv add:*)`, `Bash(git status:*)`, `Bash(git diff:*)`, `Bash(git log:*)`
- **hooks.PostToolUse** on `Write|Edit` for `*.py`: `uv run ruff format "$FILE_PATH"` then `uv run ruff check --fix "$FILE_PATH"`
- **hooks.Stop**: `timeout 120 uv run pytest -q`

Use the `update-config` skill to write it. Personal tweaks go in `.claude/settings.local.json` (make sure it's git-ignored).

Also add `.pre-commit-config.yaml` with ruff (lint + format) and mypy, then `uv run pre-commit install`.

⏸ Show me the settings diff and wait.

## Phase 5 — Quality gates

1. Run `/harness-audit` and fix anything HIGH or above.
2. Run `/security-scan` (AgentShield) against `.claude/` and hooks.
3. Add `.github/workflows/ci.yml`: on push/PR → `uv sync`, `ruff check`, `ruff format --check`, `mypy`, `pytest` (Python 3.11, `astral-sh/setup-uv`).

## Phase 6 — First commit

1. Run the **python-reviewer** and **security-reviewer** agents in parallel on everything created.
2. Address CRITICAL/HIGH findings.
3. Create branch `chore/ecc-bootstrap`, commit with `chore: bootstrap project with ECC workflow`.

⏸ Ask before pushing or opening a PR. If I approve, use `/pr`.

## Phase 7 — Hand-off

1. Update `CLAUDE.md` with anything learned (real commands, layout, gotchas).
2. Run `/save-session` so the next session can `/resume-session`.
3. Tell me which workflow to use for the first feature (normally `/orch-add-feature` with an item from `docs/PLAN.md`).

---

## After setup: daily loop

```
/resume-session              # pick up where you left off
/orch-add-feature <idea>     # or /orch-fix-defect, /orch-change-feature, /orch-refine-code
/python-review               # run before commits
/prp-commit → /pr            # ship
/save-session                # end of day
```

Periodically: `/test-coverage`, `/refactor-clean`, `/learn` (capture patterns), `/update-docs`.

## Notes

- **GateGuard** (ECC hook) asks Claude to state facts before the first Bash/Write in a session. That's expected. To silence it during setup only: `ECC_GATEGUARD=off claude`.
- ECC rules are global; this repo only needs `CLAUDE.md`, `.claude/settings.json`, and the files above.
