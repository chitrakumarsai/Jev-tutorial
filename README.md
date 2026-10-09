# Jev Audit Lens

A demo app for the team and business stakeholders. It runs the same synthetic audit tasks two ways:

- **Plain LLM:** one well-written prompt to OpenAI (`gpt-6-luna`) that reads, extracts, calculates and judges.
- **Jev + code:** code finds candidate values and does every calculation; [TypeSafe's Jev](https://docs.typesafe.ai/introduction) makes small typed judgments (Choice / Score / Noul) with calibrated confidence; low-confidence items go to an auditor review lane.

Both sides are scored against hand-written answer keys. See [docs/PRD.md](docs/PRD.md) and [docs/PLAN.md](docs/PLAN.md).

> Synthetic data only (fictional "Northwind Logistics"). Not for real audit work.

## Requirements

- Python 3.11 and [uv](https://docs.astral.sh/uv/)
- Node.js **22.14** (`nvm use` reads `.nvmrc`)

## Setup

```bash
cp .env.example .env              # add keys only if you need Live mode
export UV_CACHE_DIR=.cache/uv     # needed where ~/.cache/uv is not writable
uv sync
nvm use && npm --prefix web ci
```

## Commands

```bash
# Backend
uv run pytest                     # tests + coverage (≥ 80%)
uv run ruff check --fix .         # lint
uv run ruff format .              # format
uv run mypy src                   # strict types
uv run uvicorn jev.api.app:create_app --factory --reload --port 8000
uv run python -m jev.cli data validate    # answer key ↔ documents consistency
uv run python -m jev.cli budget init      # create the spend ledger once (needed before Live)

# Frontend (from repo root)
npm --prefix web run dev          # http://localhost:5173, proxies /api to :8000
npm --prefix web test -- --run    # unit tests
npm --prefix web run coverage
npm --prefix web run lint
npm --prefix web run typecheck
npm --prefix web run build
```

## API budget

Live calls are **off by default** (`LIVE_ENABLED=false`). When enabled, every call is checked against a hard cap of **$5.00 per API key** (OpenAI and TypeSafe), tracked in a git-ignored ledger. Replay mode uses recorded real responses and costs nothing.

## Pinned tool versions (verified 2026-10-09)

| Package | Version | Note |
|---|---|---|
| typesafe-sdk | 0.7.2 | ships `py.typed` |
| openai | 3.26.1 | |
| fastapi / uvicorn | 0.143.0 / 0.54.0 | |
| pydantic / pydantic-settings | 2.14.0 / 2.15.0 | |
| vite / react / motion | 8.3.4 / 19.3.0 / 14.0.0 | |
| typescript | **6.0.3** | not 7.x: typescript-eslint 8.71.1 supports TypeScript < 6.1 |
| vitest / jsdom | 5.0.3 / **29.1.1** | jsdom 30 requires Node ≥ 22.22 |
| eslint / typescript-eslint / prettier | 10.12.0 / 8.71.1 / 3.9.9 | |
