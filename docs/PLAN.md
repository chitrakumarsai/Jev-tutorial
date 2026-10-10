# Jev Audit Lens — Implementation Plan (Milestone 1)

> Source of truth for requirements: [PRD.md](PRD.md). This plan covers **PRD phases 1–5 = the S1 MVP**.
> Produced by the `architect` + `planner` agents (merged and reconciled), 2026-10-09.
> All package versions and model names below were verified against PyPI / npm / OpenAI docs on 2026-10-09.

## 0. Verified inputs

| Area | Choice |
|---|---|
| Python | 3.11 via `uv` (existing `.venv/`). `UV_CACHE_DIR` must point to a writable dir in this environment |
| Backend | `typesafe-sdk` 0.7.2 · `openai` 3.26.1 · `fastapi` 0.143.0 · `uvicorn` 0.54.0 · `pydantic` 2.14.0 · `pydantic-settings` 2.15.0 · `pytest-asyncio` 1.4.0 |
| Frontend | Node **22.14.0** (nvm, pinned via `.nvmrc`) · `vite` 8.3.4 · `react` 19.3.0 · `@vitejs/plugin-react` 6.1.2 · `motion` 14.0.0 · `typescript` 7.0.2 · `vitest` 5.0.3 · `@testing-library/react` 16.3.3 · `@playwright/test` 1.64.0 |
| Jev | `jev-latest` → `jev-1.13.0`; $0.042 / 1M input tokens, output free; 64k context (32k state + longest question); Choice ≤ 255 options; Score 2–10 levels |
| Baseline LLM | **`gpt-6-luna`** ($0.10 / $0.50 per 1M in/out), configurable via `OPENAI_MODEL`; Structured Outputs via `client.responses.parse(text_format=…)` |
| Budget | **Hard cap $5.00 lifetime per API key**, enforced in code |

Both SDKs use `httpx2`, so `respx` cannot intercept them → **tests mock at our own Protocol boundary** (fakes), never at HTTP.

---

## 1. Architecture

```
 web/ (Vite + React + Motion)                      src/jev/ (FastAPI, 1 uvicorn worker, 127.0.0.1)
 ┌──────────────────────────┐   /api (Vite proxy)  ┌──────────────────────────────────────────────┐
 │ RunBar · BudgetMeter     │ ── POST /runs ─────► │ api/ ──► runs.RunService                     │
 │ DocumentPane (spans)     │ ◄─ SSE /events ───── │           │ preflight ──► budget.BudgetGuard  │
 │ JevPipeline · LlmPane    │ ◄─ GET /runs/{id} ── │           ▼                  │ var/ledger.jsonl│
 │ Ledger · ReviewLane      │                      │ scenarios.registry ─► S1/S2/S3 pipelines      │
 │ Scorecard · TraceLine    │                      │   (jev side, llm side) ── RunContext          │
 └──────────────────────────┘                      │        │ JevPort        │ LlmPort             │
                                                   │  Budgeted(Recording(Live*Client))  [Live]     │
                                                   │  Replay*Client(recording)          [Replay]   │
                                                   │  scoring.Scorecard ◄── answer_key.json        │
                                                   └──────────────────────────────────────────────┘
```

**Live run:** `POST /api/runs {mode: live}` → `RunService` builds a `CostPlan` from each pipeline's `plan()` → `BudgetGuard.preflight` (whole run incl. ×3 repeats; refuses with 409 `BUDGET_EXCEEDED` before any call) → 202 `{runId, estimate}` → UI opens SSE → both sides run concurrently → each provider call: **reserve** worst-case cost → call → **commit** actual cost from `usage` → record raw response → pipelines emit `RunEvent`s → scorer → `run_completed`.

**Replay run:** identical path, but ports are `ReplayJevClient` / `ReplayLlmClient` serving **recorded real responses** by canonical request hash. The real pipeline code re-runs. No budget use. Events are paced by recorded latencies. Provenance `recorded` (model, recorded_at). A missing hash fails loudly with `REPLAY_STALE`; it never falls back to a live call.

One code path for both modes: the UI plays a **timeline of real stage events**, so the animation never fakes latency.

### Directory layout

```
src/jev/
  config.py                 # pydantic-settings: SecretStr keys, caps, prices, models, threshold, LIVE_ENABLED
  domain/                   # documents.py (Document, SpanRef) · findings.py · results.py · money.py (Decimal)
  providers/
    jev/                    # types.py · port.py (JevPort) · live.py (AsyncTypeSafeClient adapter) · confidence.py
    openai/                 # port.py (LlmPort) · live.py (responses.parse adapter) · tokens.py (conservative estimator)
  budget/                   # pricing.py · estimator.py · ledger.py (JSONL + flock) · guard.py (BudgetGuard + Budgeted* wrappers)
  replay/                   # models.py · store.py · hashing.py · clients.py (Recording*/Replay*)
  extraction/               # candidates.py (regex → Candidate w/ spans) · dates.py (date-part Choices) · text.py (sections, find_quote)
  scenarios/
    base.py · registry.py
    s1_reconciliation/      # documents.py · jev_questions.py · jev_pipeline.py · reconcile.py · llm_pipeline.py · prompt.md · scorer.py
    s2_clause_review/       # milestone 2
    s3_citation_check/      # milestone 2
  scoring/                  # answer_key.py · scorecard.py
  runs/                     # service.py · events.py · store.py (in-memory)
  api/                      # app.py · deps.py · schemas.py · sse.py · routes/{scenarios,runs,budget}.py
  cli.py                    # record <scenario> · budget show|adjust · data validate
tests/                      # mirrors src/jev/; tests/fakes/; tests/golden/ (pipelines over committed replays)
data/
  scenarios/s1_reconciliation/{manifest.json, documents/msa.md, documents/invoices/inv-2026-01.md … -12.md, answer_key.json}
  replays/s1_reconciliation/{recording_id}.json
var/ledger.jsonl            # git-ignored
web/                        # .nvmrc = 22.14.0
  src/app/App.tsx
  src/features/{scenario-picker,documents,run-control,pipeline,llm-pane,ledger,review-lane,scorecard,trace}/
  src/components/ui/{Button,SurfaceCard,ProvenanceBadge,Money}.tsx
  src/hooks/{useRunEvents.ts,useSpanRegistry.ts}
  src/lib/{api.ts,types.ts,runReducer.ts,money.ts}
  src/styles/{tokens.css,typography.css,global.css}
```

### Key interfaces (abridged)

```python
class JevPort(Protocol):                     # our types, never SDK types
    async def evaluate(self, req: JevRequest) -> JevResult: ...
class LlmPort(Protocol):
    async def parse(self, req: LlmRequest, schema: type[T]) -> LlmResult[T]: ...
class BudgetGuard(Protocol):
    def preflight(self, plan: CostPlan) -> BudgetDecision: ...
    async def reserve(self, provider: Provider, est: Decimal) -> Reservation: ...   # raises BudgetExceeded
    async def commit(self, r: Reservation, actual: Decimal | None) -> None: ...     # None → keep estimate
class ScenarioPipeline(Protocol):           # makes S1/S2/S3 pluggable
    side: Literal["jev", "llm"]
    def plan(self, docs: DocumentSet) -> CostPlan: ...                            # no I/O
    async def run(self, docs: DocumentSet, ctx: RunContext) -> SideResult: ...
```

Ledger line: `{ts, provider, key_fp: sha256(key)[:12], kind: reserve|commit|release|adjust, usd: "0.0123", run_id}`. The key itself is never stored.

UI-facing types (Python and TS mirror each other, checked by a shared JSON fixture in pytest + vitest): `SpanRef {docId,start,end,text}` (backend asserts `doc[start:end] == text`) · `Judgment {primitive, answer, probabilities?, confidence, orderCheck?}` · `Finding {kind, billed?, expected?, variance? (Decimal strings), evidence: SpanRef[], traceable, confidence, lane: auto|review, reviewReason?}` · `Metrics {latencyMs, requests, inputTokens, outputTokens, costUsd}` · `Provenance {kind: live|recorded, model, recordedAt?}` · `Scorecard {items[{keyId, status: correct|correct_in_review|wrong_value|missed}], falsePositives, totals}` · `RunEvent` (step / finding / side_completed / run_completed / error).

### API (JSON envelope `{success, data, error}`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness |
| GET | `/api/scenarios`, `/api/scenarios/{id}/documents`, `/api/scenarios/{id}/recordings` | catalogue, document text, available replays |
| GET | `/api/budget` | spent / cap per provider (never keys) |
| POST | `/api/runs/estimate` | pre-flight cost estimate |
| POST | `/api/runs` | `{scenarioId, mode, repeat: 1\|3, recordingId?}` → 202; 409 `BUDGET_EXCEEDED`; 403 `LIVE_DISABLED`; 409 `RUN_IN_PROGRESS` |
| GET | `/api/runs/{id}/events` | **SSE** stream of `RunEvent` (StreamingResponse, no extra dependency) |
| GET | `/api/runs/{id}` | final `RunResult` |

Recording is **CLI-only** (`uv run python -m jev.cli record s1`, typed confirmation), which keeps the live-spend surface small.

---

## 2. S1 Jev pipeline (respects Jev 1.13 weak spots)

1. **Code: filter.** Split the MSA into sections and keep only rate / discount / surcharge / late-fee / term sections (small state). Parse invoices into header + line rows.
2. **Code: candidates.** Over-finding regexes for money, %, quantities and years → `Candidate{value, docId, start, end, line}`. Duplicate values get line-suffixed option keys. Every pick has a `none` option.
3. **Jev request 1: contract terms** (~2–4k tokens, ~18 parallel questions). Choice picks for each rate, discount threshold and %, surcharge cap, late fee. A **reversed-order twin** for the 5 key picks: if a twin disagrees, the item goes to review. Effective-date parts as Choices.
4. **Jev requests 2–13: one per invoice** (~0.5–1k tokens each, concurrency 4): date parts; per line a `line_kind` Choice plus value picks; a duplicate-shipment Noul only for pairs that code has already found to have equal amounts.
5. **Code: maths.** Real dates from parts; cumulative volume; discount-eligibility month; expected charges; surcharge vs. cap; variances and total, all `Decimal`, `ROUND_HALF_UP` to cents.
6. **Code: gate.** A finding's confidence is the minimum over the judgments it used (Noul confidence = `|2p−1|`, per `confidence.md`). It goes to **review** if confidence < 0.8, a required pick is `none`, an order twin disagrees, or a date can't be assembled. The reason is shown on the card.
7. **Limits.** `StatePacker` refuses if state + longest question > 28k tokens (margin under 32k) and then picks section first, span second. `ChoiceQ` rejects > 255 options.

**LLM side:** one `responses.parse` call with a Pydantic schema (amounts as strings, each finding must include a verbatim `quote`). Code runs `find_quote` against the documents: found → `SpanRef`; not found → `traceable=false`. Both sides get the same traceability test, which keeps the comparison fair.

---

## 3. Task list

Shared verification:
- **V-py:** `uv run pytest && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
- **V-web:** `npm --prefix web run lint && npm --prefix web run typecheck && npm --prefix web run test -- --run && npm --prefix web run build`

Sizes: S < 2h · M ≈ ½ day · L 1–2 days · ∥ = can run in parallel.

### Phase A: Bootstrap (ECC_SETUP phases 3–6)

| ID | Task | Acceptance | Size | Deps |
|---|---|---|---|---|
| B1 | `uv init --package --name jev --python 3.11` (keep `.venv/`, `.gitignore`); add runtime + dev deps at the verified versions; tool config **exactly per ECC_SETUP** (ruff 100 / py311 / `E,F,I,B,UP,SIM,S,N`; mypy strict, `files=["src"]`; pytest cov ≥ 80); `src/jev/__init__.py`, `tests/test_smoke.py`, `.env.example` (`TYPESAFE_API_KEY=`, `OPENAI_API_KEY=`, `OPENAI_MODEL=gpt-6-luna`, `LIVE_ENABLED=false`), `README.md` | V-py green | S | – |
| B2 | FastAPI `create_app()` + `GET /api/health` (test first) | 200 `{success:true,data:{status:"ok"}}` | S | B1 |
| B3 ∥ | `web/` Vite react-ts at verified versions, `.nvmrc`, `engines.node >=22.12`, scripts `dev/build/typecheck/lint/format/test/test:e2e`, `/api` proxy to `127.0.0.1:8000`; one RTL smoke test | `nvm use && V-web` green | M | B1 |
| B4 | `.claude/settings.json` via `update-config`: ECC allowlist + scoped `npm --prefix web run …` / `npm --prefix web ci`; **no** blanket `npm install` / `npx`. PostToolUse hook script formats + lints `*.py` (ruff) and `web/**` (prettier + eslint). Stop hook: `timeout 120 uv run pytest -q` + web unit tests. `UV_CACHE_DIR` in `.claude/settings.local.json` (git-ignored). Git-ignore `.env`, `var/`, `.uv-cache/`, `web/node_modules`, `web/dist`, `playwright-report/` | ⏸ settings diff shown | S | B1, B3 |
| B5 | `.pre-commit-config.yaml` with `repo: local` hooks (ruff, ruff-format, mypy, web lint + typecheck), so versions come from the lockfiles; `uv run pre-commit install` | `uv run pre-commit run --all-files` | S | B4 |
| B6 | `.github/workflows/ci.yml`: **python** job (setup-uv, 3.11, `uv sync --locked`, ruff, format check, mypy, pytest) + **web** job (setup-node from `.nvmrc`, `npm ci`, lint, typecheck, vitest + coverage, build). No secrets; `LIVE_ENABLED=false`; actions pinned to SHAs | both jobs green | S | B5 |
| B7 | `/harness-audit`, `/security-scan`; python-reviewer + security-reviewer + typescript-reviewer in parallel; branch `chore/ecc-bootstrap`, commit `chore: bootstrap project with ECC workflow` | no CRITICAL/HIGH · ⏸ ask before push/PR | S | B6 |
| B8 | Update `CLAUDE.md` (web commands, `UV_CACHE_DIR`, nvm 22, layout); `/save-session` | – | S | B7 |

### Phase B: Synthetic data and answer key (∥ with Phase C)

| ID | Task | Acceptance | Size | Deps |
|---|---|---|---|---|
| D1 | Northwind Logistics MSA (≤ 2,000 tokens): numbered clauses. §3 rate card (Zone A $1,250.00/load, Zone B $1,480.00/load, detention $85.00/hr) · §4 volume discount 5% off line-haul from the month after cumulative contract-year loads exceed 1,000 · §5 fuel surcharge capped at 18% of line-haul · §6 late fee 1.5% if paid > 30 days after invoice date · **distractor numbers** ($2,000,000 insurance, 90-day notice, $500 admin fee) | regex over-finds the distractors | M | B1 |
| D2 | 12 monthly invoices 2026 (≤ 350 tokens each): header + 3–6 lines. Month 9 has a **legitimate** late fee (paid day 41) as a false-positive trap | – | M | D1 |
| D3 | `answer_key.json` (hand-written) + Pydantic model; test recomputes total variance with an independent `Decimal` sum | ⏸ **presenter reviews the key** | S | D2 |
| D4 | Loader + size guard + `cli data validate` (every answer-key value is findable by the regexes) | fails on oversize docs | S | D2 |

**Planted discrepancies:**
1. `discount_not_applied`: Zone A line-haul billed at $1,250.00 instead of $1,187.50 on invoices 07–12 (one finding per invoice).
2. `surcharge_over_cap`: invoice 04 bills 22% vs. the 18% cap.
3. `duplicate_line`: invoice 10 repeats a detention line (6 h × $85 = $510.00).

**Answer-key format:** `{scenario_id, version, authored_at, contract_terms{…}, items[{id, kind, doc_id, line_ref, billed, expected, variance, evidence[{doc_id, quote}]}], clean_invoices[], total_variance}`. Money is stored as decimal strings.

### Phase C: Core engine (∥ with Phase B; C2–C6 ∥ after C1)

| ID | Task | Acceptance | Size | Deps |
|---|---|---|---|---|
| C1 | `config.py` (SecretStr keys; mode defaults to replay; `LIVE_ENABLED=false`), `domain/` frozen models, `money.py` | V-py | S | B2 |
| C2 | **Budget guard**: pricing constants ("verified 2026-10-09"), estimator (input + full `max_output_tokens` × (1+retries), counting reasoning tokens as output), JSONL ledger with `flock` + `asyncio.Lock`, preflight / reserve / commit / release, **fails closed** on a corrupt ledger, $0.25 safety margin, `budget show|adjust` | tests first: refuses when spent + estimate > cap; records actual usage | M | C1 |
| C3 | `JevPort` + live adapter (`AsyncTypeSafeClient`), domain error mapping, Noul confidence; fakes in `tests/fakes/` | adapter tested with fake SDK object | M | C1 |
| C4 | `LlmPort` + OpenAI adapter (`responses.parse`, explicit `max_output_tokens`; refusal or parse failure → scored "no answer", not a crash) | – | M | C1 |
| C5 | Replay store + Recording/Replay clients; canonical request hash; `REPLAY_STALE` on a miss | a miss never calls live | M | C3, C4 |
| C6 | Answer-key model + generic scorecard (match by doc + kind; exact `Decimal`; FP count; `correct_in_review` kept separate) + metrics (usage × pricing) | coverage ≥ 80% | M | C1, D3 |

### Phase D: S1 pipeline + API

| ID | Task | Acceptance | Size | Deps |
|---|---|---|---|---|
| P1 ∥ | `extraction/candidates.py`, `text.py`, `dates.py` | distractors appear as candidates | S | D4 |
| P2 ∥ | `jev_questions.py` (picks + `none`, order twins, date parts, duplicate Noul); snapshot tests | – | M | P1 |
| P3 ∥ | **Pure `Decimal` reconciler** `reconcile.py` | reproduces the answer key exactly from hand-entered terms | M | D3 |
| P4 | `jev_pipeline.py` + review gate + `RunEvent`s | tested with fakes | M | P2, P3, C3 |
| P5 ∥ | `llm_pipeline.py` + fair `prompt.md` + `find_quote` traceability | – | S | C4 |
| P6 | `runs/service.py`: both sides concurrently, score, assemble `RunResult` | – | S | P4, P5, C5, C6 |
| P7 | API routes + SSE + envelope; CORS from env; one live run at a time; `dependency_overrides` in tests; fastapi-reviewer + security-reviewer | V-py | M | P6 |
| P8 | `cli record s1 --runs 3`: estimate shown + typed confirmation | ⏸ **first live spend needs your approval** | S | P7 |

### Phase E: UI foundation + S1 screens (MVP complete)

| ID | Task | Size | Deps |
|---|---|---|---|
| U1 | Tokens (semantic palette: verified green, review amber, discrepancy vermilion, Jev indigo, LLM slate; ink navy / paper ivory themes), self-hosted Fraunces + Inter (`font-display: swap`, tabular numerals), paper grain + ledger grid | M | B3 |
| U2 | Typed API client + runtime guards, `useRunEvents` (SSE reducer, plays timeline), `useReducedMotion` | M | P7 |
| U3 | App shell, scenario picker, document viewer with span highlighting (semantic landmarks) | M | U1, U2 |
| U4 ∥ | LLM pane: typewriter reveal of the parsed result (labelled honestly, not token streaming) | S | U3 |
| U5 ∥ | Jev pane: candidates highlight → question chips fan out → typed cards snap back, probability bars, confidence ring | L | U3 |
| U6 ∥ | Ledger tick-off, discrepancy shake, variance count-up | M | U3 |
| U7 ∥ | Review lane glide (`layoutId`), scorecard cascade, cost / latency meter, click-a-number trace line | M | U3 |
| U8 | Live / Replay toggle, "Recorded {date} · {model}" badge, budget meter, error states | S | U4–U7 |
| U9 | Playwright E2E (replay mode) + reduced-motion + axe scan; screenshots at 320 / 768 / 1024 / 1440, both themes | M | U8 |

All motion uses `transform` / `opacity` only, honours `prefers-reduced-motion`, and keeps `will-change` narrow.

---

## 4. Budget estimate (S1, one run)

Assumptions: LLM ≈ 6.5k input tokens + 2–6k output (incl. reasoning); Jev ≈ 13 requests × 2.5k ≈ 35k input tokens, output free.

| Side | Cost / run | Runs within $5 |
|---|---|---|
| **gpt-6-luna** (chosen) | ≈ $0.001–0.004 | > 1,000 |
| Jev | ≈ $0.0015 | > 3,000 |
| *(footnote)* gpt-6.1-sol / gpt-6-astra | ≈ $0.03–0.07 / $0.17–0.37 | ≈ 70–150 / 13–29 |

Milestone 1 target: **< $0.50 spent per key**. A ×3 consistency demo needs **3 separate live recordings** (replaying one recording 3 times would be trivially identical), labelled as such.

---

## 5. Key decisions (ADR summary)

| # | Decision | Why | Trade-off |
|---|---|---|---|
| 1 | Own provider Protocols + adapters; fakes in tests | Deterministic, zero-spend tests; works with httpx2 | More mapping code |
| 2 | Replay = recorded raw responses re-run through real pipeline | Honest; recordings double as golden tests | Pipeline edits make recordings stale → re-record (Jev ≈ free, luna ≈ cents) |
| 3 | Budget: preflight + reserve/commit, JSONL ledger, key fingerprint, fail closed | Hard stop before overspend | Pessimistic token estimates |
| 4 | Live off by default; Replay default | Rehearsals can't spend | One env step before the live demo |
| 5 | One Jev request per document | Small state = better accuracy | 13 requests (concurrent, negligible cost) |
| 6 | Order-check twins on key picks | Shows a known weakness being mitigated | 2× questions on 5 picks |
| 7 | Decimal strings end-to-end; UI never does maths | Ties to the cent | Formatting helper needed |
| 8 | SSE for run events | Real step timing drives animation; same path for replay | Reconnect handling via `GET /runs/{id}` |
| 9 | In-memory run store, single worker, bind 127.0.0.1 | Single presenter, local | Not scalable (not required) |
| 10 | Baseline `gpt-6-luna` | Presenter decision; cheapest current model | Audience may ask "what about a bigger model?" (see open questions) |

## 6. Risks

| Risk | Mitigation |
|---|---|
| TypeScript 7.0.2 vs. typescript-eslint compatibility | Decide in B3; fall back to non-type-aware lint rules or a separate `tsc` typecheck |
| Unverified versions (eslint, prettier, coverage-v8, axe, GH actions) | Pin at install time, record in README |
| `typesafe-sdk` may lack `py.typed` → strict mypy fails | Typed adapter + targeted mypy override for that import only |
| Reasoning tokens make estimates uncertain | Reserve worst case (`max_output_tokens`), commit actual |
| LLM matches Jev on accuracy | Answer key fixed in advance; report honestly; story leans on review lane, traceability, cost |
| Review-lane scoring looks like cherry-picking | Policy fixed before any run: `correct_in_review` reported separately, not counted as auto-correct |
| Key / body leakage | SecretStr; never enable SDK debug logging; bind 127.0.0.1; CORS to Vite origin only; API returns key fingerprints only |
| Accidental live spend in tests / CI | Live off by default; replay miss raises; CI has no keys; ledger fails closed |

### Additional safeguards (from the planner's revised pass)

- **Network guard in tests:** `tests/conftest.py` blocks real sockets, so any accidental live call fails the test run.
- **Cap can only go down:** `BUDGET_CAP_USD` may be lowered via env; values above 5.00 are rejected at startup.
- **Jev billing granularity is unverified:** is input billed once per request, or per question (state + question)? C3 must confirm from the returned `usage` before the estimator is finalised. Until then the estimator assumes the pessimistic per-question case (≈ $0.003–0.008 per S1 run, still > 600 runs within $5).
- **Hook mechanics:** Claude Code passes the edited file path as JSON on stdin (not `$FILE_PATH`). The hook script also sources nvm and honours `.nvmrc`, because non-interactive shells otherwise pick the system Node 18. Verify in B4.
- **Recordings never store headers or keys**; `security-reviewer` checks `data/replays/` before every commit.
- **Unknown model → no Live:** the pricing table holds only the verified models; any other `OPENAI_MODEL` refuses Live (can't estimate cost).
- **Jev alias drift:** record the resolved model per response and warn if it isn't `jev-1.13.*` (questions are tuned to 1.13's weak spots).
- **Fairness:** the exact LLM prompt and model are shown in the UI.
- **SSE through the Vite proxy:** test for buffering in U2; `GET /api/runs/{id}` is the fallback.

## 7. Decisions (accepted by presenter, 2026-10-09)

1. **pyproject additions beyond ECC_SETUP:** `per-file-ignores "tests/**" = ["S101"]` and `asyncio_mode = "auto"`: **accepted**.
2. **S1 knock-on surcharge** (18% surcharge computed on the undiscounted base) is a **separate itemised finding**: **accepted**.
3. **Review-lane scoring:** `correct_in_review` is reported separately and **not** counted as auto-correct: **accepted**.
4. **Baseline model:** `gpt-6-luna` only; no bigger-model run: **accepted**.
