# Jev Audit Lens — Implementation Plan (Milestone 2)

> Source of truth: [PRD.md](PRD.md) Phase 6 (**S2 + S3**). Builds on [PLAN.md](PLAN.md) (Milestone 1, S1 MVP, complete with U9 / PR #17) and the ADRs in [adr/](adr/).
> Drafted 2026-10-10. **Status: approved by the presenter 2026-10-10** (decisions in §8 accepted as recommended).
> Success (PRD): all three scenarios scored and animated, and S2 counts toward the headline metric (Jev accuracy ≥ LLM on the S1 **and** S2 answer keys across 3 runs).

---

## 0. Requirements restated

| | S2: Agreement clause risk review | S3: Citation check of an LLM-written audit memo |
|---|---|---|
| **Question** | Does the agreement contain each clause on a fixed audit checklist, where is it, and how risky are its terms? | Does each citation in an audit memo actually support the claim it is attached to? |
| **Trap** | One required clause is **missing**; one is present under a misleading heading; one heading exists but its text says something else | Planted bad citations: a **fabricated** quote, a **contradicted** claim, an **unsupported** claim (verbatim quote that doesn't prove the claim), and a mis-numbered section |
| **Jev + code** | Line-numbered state; per clause one parallel `Choice` (which line) + `Noul` (does any line address it) + `Score` (risk rubric); code maps `exists` to present / absent / partial and gates on confidence | Code first: quote substring match (normalised); not found → `fabricated`, no model call. Otherwise one `Choice` `relation` ∈ {supports, contradicts, says_nothing} per citation; 0.8 confidence gate |
| **LLM** | One `responses.parse` call: checklist in, per-clause `{present, section, quote, risk}` out | One `responses.parse` call: memo + sources in, per-citation verdict + reason out |
| **Shows** | Parallel typed questions; honest "not present" instead of a confident invented clause | "Better together": the LLM writes prose, Jev verifies it, code does exact string checks |

Both sides keep S1's fairness rules: identical documents, the exact LLM prompt shown in the UI, the same `find_quote` traceability test for any quote either side returns, and answer keys written by hand **before** any model run.

---

## 1. Grounding: what exists and what is S1-only today

Patterns to mirror (keep, don't reinvent):

| Category | Source | Pattern |
|---|---|---|
| Pipelines | `src/jev/scenarios/s1_reconciliation/{jev_pipeline,llm_pipeline,llm_schema}.py` | A `JevS1Pipeline` / `LlmS1Pipeline` pair: `request()` / `plan()` without I/O, `run()` emitting `step` / `finding` events, returning `SideOutput` |
| Jev types | `src/jev/providers/jev/types.py` | Our own `ChoiceQ` / `ScoreQ` / `NoulQ` / `JevRequest` (≤ 255 options, 2–10 score levels); pipelines never import SDK types |
| Findings | `src/jev/domain/findings.py` | One frozen `Finding` for both sides; `SpanRef` evidence; `lane` auto/review + `review_reason`; `traceable` |
| Answer keys | `src/jev/scoring/answer_key.py` + `data/scenarios/s1_reconciliation/answer_key.json` | Frozen Pydantic, validated on load (e.g. variance = billed − expected) |
| Errors | `src/jev/runs/service.py` `NoRecordingError`, `src/jev/providers/errors.py` | Domain exceptions mapped to envelope errors in `api/errors.py` |
| Replay | `src/jev/replay/*`, `data/replays/<scenario>/` | Canonical request hash; a miss raises `REPLAY_STALE`, never calls live |
| Tests | `tests/` mirrors `src/jev/`; fakes in `tests/fakes/`; golden tests over committed replays | pytest, AAA, `dependency_overrides` for API tests |
| UI | `web/src/features/*`, `web/e2e/*` | Feature folders, RTL tests by role, Playwright replay journeys + axe + screenshots |

**S1 is hard-wired** (the registry in PLAN.md §1 was never built). These must be generalised first:

| Where | S1 coupling |
|---|---|
| `runs/service.py` | imports `JevS1Pipeline`, `LlmS1Pipeline`, `S1LlmReport`, `load_s1_documents`, `SCENARIO_ID` |
| `api/routes/scenarios.py`, `api/routes/runs.py` | 404 for any id other than `SCENARIO_ID`; single hard-coded `ScenarioSummary` |
| `cli.py` | `data validate` and `record` only know S1 |
| `scoring/answer_key.py` | `FindingKind` and `KeyItem` are money-only (billed / expected / variance) |
| `scoring/scorecard.py` | statuses include `wrong_amount`; `total_variance_*` fields |
| `web/src/features/results/Results.tsx`, `features/ledger/*` | rows "Wrong amounts", "Total variance"; ledger rows render billed / expected / variance |

---

## 2. Architecture changes

1. **Scenario registry** `src/jev/scenarios/registry.py`: a frozen `ScenarioSpec` per scenario with `id`, `title`, `description`, `load_documents()`, `load_answer_key()`, `build_pipelines(docs, settings, run_id) -> (JevPipeline, LlmPipeline)`, `llm_schema`, `llm_instructions`, `scorer`, `validate_data()`. `RunService`, routes and CLI look the scenario up by id (unknown → 404 `SCENARIO_NOT_FOUND`). S1 moves behind it with **no behaviour change** (its golden replays must still pass byte-for-byte).
2. **Scoring per scenario.** A `Scorer` protocol returns a generic `Scorecard {items[{key_id, status, label}], false_positives, summary: list[SummaryRow]}`. Statuses become a superset: `correct | correct_in_review | wrong_value | missed`, and S1 maps `wrong_amount` → `wrong_value` (UI label stays "Wrong amounts" for S1 via the summary rows). Scenario-specific totals (S1 total variance) move into `summary` rows the UI renders as given, so `Results.tsx` stops knowing about money.
3. **Finding gains optional, typed detail** (still one model, still frozen): `kind` widens per scenario; new optional fields `verdict` (`present | absent | partial` for S2; `verified | unsupported | contradicted | fabricated` for S3), `risk` (S2 rubric level), `claim` (S3). Money fields stay optional. The TS mirror and the shared JSON fixture are regenerated (`npm run gen:api`).
4. **Answer keys**: a discriminated union `S1Key | S2Key | S3Key` on `scenario_id`, each validated on load (S2: every checklist item has exactly one status and, if present, a quote that exists in the agreement; S3: every citation id in the memo has exactly one expected verdict, and every `fabricated` quote is provably absent from the sources).
5. **UI**: the ledger row renders by `verdict` / money presence (money row as today; clause row: status + section + risk chip; citation row: verdict badge + claim + quote). Results renders `summary` rows from the API. The scenario picker already lists the catalogue.

ADR to add: **0004 Scenario registry and per-scenario scoring** (why generic `summary` rows instead of per-scenario result components).

---

## 3. S2 design: clause risk review

**Data (`data/scenarios/s2_clause_review/`)**: a second Northwind Logistics document, a **Data Processing & Services Addendum** (≤ ~180 numbered lines so one `Choice` over lines fits the 255-option cap) plus a fixed **audit checklist** of ~10 clauses: limitation of liability, indemnity, termination for convenience, auto-renewal, governing law, data protection / breach notice, audit rights, insurance, subcontracting, payment terms. Planted:
- **Missing**: no breach-notification clause (the trap: an LLM tends to invent "within 72 hours").
- **Misleading heading**: "Audit" heading whose text only covers invoice disputes, not audit rights → partial.
- **Risky term**: liability cap of 1 month's fees (high risk) vs. market 12 months.
- **Distractor**: the MSA's insurance clause is referenced by number but not repeated (present-by-reference → partial).

**Jev pipeline** (per Jev 1.13 guidance, one state, parallel questions):
1. Code: split into lines `L000…`, drop blank lines, build the line-numbered state once.
2. Jev request (one call, ~10 clauses × 3 questions = ~30 parallel questions; the semantic-find recipe sends the document once): per clause `where` (Choice over line ids), `exists` (Noul), `risk` (Score, 4-level rubric written in the checklist). If the addendum exceeds 255 lines: two-pass window then line (recipe caveat).
3. Code: `exists ≥ 0.7` present, `< 0.35` absent, else partial (thresholds from the recipe, tuned on our data before the key review and then frozen); risk only reported when present. Evidence = the picked line's span. Gate to review if confidence < 0.8, verdict partial, or `where` and `exists` disagree (high `where`, low `exists`).

**LLM pipeline**: one call, schema per clause `{clause_id, present: bool, section: str|None, quote: str|None, risk: low|medium|high|critical|None}`; `find_quote` makes quotes traceable or not; a "present" claim with an untraceable quote is scored as a fabricated clause.

**Scoring**: per checklist item: correct status; when present, correct line/section (± the clause's line range in the key) and correct risk level → `wrong_value` if status right but risk/location wrong; false positive = absent clause reported present.

---

## 4. S3 design: citation check

**Data (`data/scenarios/s3_citation_check/`)**: the sources are the **S1 documents** (MSA + invoices, reused by reference, not copied) plus an **audit memo** (~600 words, ~10 numbered citations `[C1]…[C10]`, each `{claim, quote, doc, section}`).

**Decision D-1 (accepted 2026-10-10: option a): where the memo comes from.** A live LLM memo can't have an answer key written in advance, which the PRD requires. Recommended: **generate the memo once with `gpt-6-luna` from the S1 documents (one small live call, approved), commit it, then the presenter plants 4 errors by hand** (fabricated quote, contradicted claim, unsupported verbatim quote, wrong section) and writes the key. The memo is labelled "LLM-drafted, errors planted for the demo" in the UI. Alternatives: (b) memo fully hand-written (no spend, less authentic); (c) live memo each run with no scorecard (most authentic, but S3 then has no objective score).

**Jev pipeline** (citation-check recipe):
1. Code: normalise whitespace / curly quotes; quote not found in the named document → `fabricated`, confidence `None`, auto lane, **no Jev call**.
2. Jev: one request per remaining citation (state = `{claim, section}`; the section is found by code from the citation's section ref), `relation` Choice; requests run with concurrency 4 like S1's invoices. Gate: confidence < 0.8 → review.
3. Code: wrong section ref (quote found but in another section) → noted on the finding (not a separate verdict).

**LLM pipeline**: one call: memo + sources in; per citation `{citation_id, verdict, reason}` out (the "LLM checks its own kind" baseline).

**Scoring**: per citation verdict exact match; `correct_in_review` kept separate as in S1; false positive = a correct citation flagged as bad.

---

## 5. Task list

Legend: ∥ = can run in parallel with siblings · ⏸ = needs presenter approval · sizes S/M/L.

### Phase F: Generalise (behaviour-preserving for S1)

| ID | Task | Gate | Size | Deps |
|---|---|---|---|---|
| R1 | ADR 0004; `ScenarioSpec` + registry; S1 registered; `RunService`, routes, CLI look up by id; unknown id → 404 `SCENARIO_NOT_FOUND` (tests first) | S1 golden replays + all existing tests unchanged | M | – |
| R2 | Generic `Scorecard` (`wrong_value`, `summary` rows) + `Scorer` protocol; S1 scorer ported; OpenAPI + `schema.gen.ts` regenerated | S1 scorecard JSON equivalent; web unit tests green | M | R1 |
| R3 | `Finding` optional `verdict` / `risk` / `claim`; answer-key discriminated union; shared JSON fixture updated | pytest + vitest fixture checks | S | R1 |
| R4 | UI: Results renders API `summary` rows; ledger row switches on finding shape; scenario picker shows 3 entries | S1 E2E + screenshots unchanged | M | R2, R3 |

### Phase G: Data and answer keys (∥ with Phase F)

| ID | Task | Gate | Size | Deps |
|---|---|---|---|---|
| D5 ∥ | S2 addendum + checklist (with clause rubric text) + `answer_key.json`; `data validate` checks (every present quote exists; absent clause has no matching line by keyword search) | ⏸ **presenter reviews the S2 key** | M | – |
| D6 ∥ | S3 memo per D-1 + citations + `answer_key.json`; validate (fabricated quotes provably absent; others found) | ⏸ **presenter approves D-1 and reviews the S3 key** (option a: one live call, estimate shown first) | M | – |

### Phase H: S2 and S3 pipelines + API

| ID | Task | Gate | Size | Deps |
|---|---|---|---|---|
| S2a | `scenarios/s2_clause_review/`: line splitter, questions (snapshot tests), Jev pipeline with fakes, gate | coverage ≥ 80% | M | R3, D5 |
| S2b ∥ | S2 LLM pipeline + `prompt.md` + schema + `find_quote` | – | S | R3, D5 |
| S2c | S2 scorer + registry entry | scorer tests against hand-built findings | S | R2, S2a, S2b |
| S3a ∥ | `scenarios/s3_citation_check/`: quote normaliser, section locator, Jev pipeline (fabricated short-circuit) with fakes | coverage ≥ 80% | M | R3, D6 |
| S3b ∥ | S3 LLM pipeline + prompt + schema | – | S | R3, D6 |
| S3c | S3 scorer + registry entry | – | S | R2, S3a, S3b |
| P9 | Reviews: python-reviewer, fastapi-reviewer, security-reviewer (new data files, prompts, no keys in recordings) | no CRITICAL/HIGH | S | S2c, S3c |
| P10 | `cli record s2|s3 --runs 3`: estimate shown + typed confirmation | ⏸ **live spend: your approval per recording** | S | P9 |

### Phase I: UI + E2E

| ID | Task | Gate | Size | Deps |
|---|---|---|---|---|
| U10 ∥ | S2 Jev pane: clause chips fan out (one per checklist item), "not present" card state (distinct shape + icon, not colour only), risk chip; line highlight in the document viewer | RTL tests by role | M | R4, S2c |
| U11 ∥ | S3 panes: memo viewer with citation markers; verdict badges (verified / unsupported / contradicted / fabricated) with text labels; fabricated shown as "quote not in source" without a Jev call animation | RTL tests | M | R4, S3c |
| U12 | E2E: replay journeys for S2 and S3 (picker → replay → results), axe both themes, reduced-motion recorder, screenshots 4 widths × 2 themes per scenario; docs (README, CLAUDE.md) | CI e2e green | M | U10, U11, P10 |

Order: R1 → (R2, R3) → R4, with D5/D6 in parallel from day one. S2 and S3 tracks are independent after R3.

---

## 6. Budget estimate (recording 3 runs each)

From measured S1 figures (memory: Jev bills input once per request ≈ 0.5 tok/char + 256; luna ≈ 2–4k reasoning + ~2k answer, output cap 16k):

| Scenario | Jev requests / run | LLM calls / run | Est. per run | 3 runs |
|---|---|---|---|---|
| S2 | 1 (≈ 6–8k input tokens) | 1 | ≈ $0.003–0.006 | ≈ $0.02 |
| S3 | ≤ 10 small (≈ 1–2k each) | 1 (memo + sources, ≈ 8k in) | ≈ $0.004–0.008 | ≈ $0.03 |
| D-1 (a) memo draft | 0 | 1 | ≈ $0.003 | – |

Well within the $5 cap per key. Each recording still needs your explicit approval and the typed `RECORD` confirmation; re-check ledger headroom first (there is no `budget show` command yet; add one in P10 or read `var/ledger.jsonl` totals).

---

## 7. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Registry refactor changes S1 behaviour or replay hashes | Medium | R1 is test-first; S1 golden replays and E2E screenshots must pass unchanged; no request content changes |
| S2 addendum > 255 lines | Low | Keep ≤ 180 numbered lines; two-pass window only if needed |
| `exists` thresholds (0.7 / 0.35) don't separate our clauses | Medium | Tune once on the addendum with fakes + a single approved live probe, then freeze **before** the key review; a misleading-heading clause is designed to land in "partial" → review |
| S3 key can't exist for a live memo | High if (c) | Decision D-1; recommended (a) |
| LLM matches Jev on S2 | Medium | Report honestly (PRD risk table); the story leans on "not present" handling, review lane and traceability |
| Finding / scorecard schema change breaks the UI | Medium | Regenerate `schema.gen.ts`; CI already diffs it; R4 behind S1 E2E |
| Jev 1.13 weak spots (dates, arithmetic) | Low | S2/S3 ask no maths or date questions; code does all comparisons (ADR 0001) |
| iCloud " 2" duplicate files after branch switches | Medium | `cmp` before deleting (memory) |

---

## 8. Decisions (accepted by presenter, 2026-10-10)

1. **D-1: S3 memo source**: **(a) accepted**: LLM-drafted once (approved live call) + errors planted by hand. Rejected: (b) fully hand-written, (c) live each run without a scorecard.
2. **S2 document**: **a new Northwind Data Processing & Services Addendum: accepted** (the S1 MSA was written for pricing, not clause risk).
3. **Generic results shape**: **API-driven `summary` rows: accepted** (not a results component per scenario).
4. **Scope**: **accepted**: consistency runs (repeat = 3 in the UI) stay in Phase 7, not here.

## 9. Complexity

**Overall: Large.** Phase F ≈ M (careful refactor), data ≈ M with presenter review time, S2 and S3 tracks ≈ M each, UI + E2E ≈ M. Roughly 9 PR-sized slices: R1, R2–R3, R4, D5+D6, S2, S3, P9–P10, U10–U11, U12.

## 10. Acceptance

- [ ] S1 unchanged (golden replays, E2E, screenshots) after Phase F
- [ ] S2 and S3 answer keys reviewed by the presenter before any recording
- [ ] All three scenarios run in replay, are scored, and animate; reduced motion and axe pass
- [ ] Recordings for S2/S3 (3 runs each) with approval; spend within cap
- [ ] Coverage ≥ 80% (Python and web); reviewers no CRITICAL/HIGH
