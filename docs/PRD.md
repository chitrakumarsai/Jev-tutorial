# Jev Audit Lens — PRD

## Problem Statement

Audit and finance staff experimenting with AI, and the business leaders deciding whether to invest in it, get confident but unverifiable answers from general-purpose LLMs: wrong or mistyped numbers, invented clauses, and no signal of when to trust an answer. For audit evidence that is unacceptable, so every output must be re-checked by hand, erasing the time saved and blocking adoption.

## Evidence

- PCAOB 2025 inspection priorities flag generative-AI use in audits; a hallucinated document summary does not meet audit-evidence standards ([Trullion](https://trullion.com/blog/ai-hallucination-in-accounting-and-audit/)).
- DataSnipper's 2026 AI Report: trust in AI to deliver quality fell from 78% to 55% in one year; preparers of AI-assisted work trust it least (50%); top concerns are traceability and outputs they cannot easily validate ([idp-software](https://idp-software.com/vendors/datasnipper/)).
- TypeSafe's own docs state LLMs are a mismatch for decisions code must consume, and that Jev is calibrated but "not a calculator", so the honest architecture is Jev for judgments + code for maths ([docs.typesafe.ai](https://docs.typesafe.ai/introduction), [jaggedness](https://docs.typesafe.ai/model-jaggedness/jev-1.13)).
- Internal evidence (a specific incident or request driving this demo): **TBD — needs input from presenter**.

## Proposed Solution

A demo web app that runs the same synthetic audit tasks two ways, side by side: (1) a plain OpenAI LLM given one well-written prompt with structured JSON output, and (2) a **Jev + code** pipeline where code finds candidate values and performs all arithmetic and date logic, Jev makes small typed judgments (Choice / Score / Noul) with calibrated confidence, and low-confidence items are routed to an "Auditor review" lane. Both sides are scored against a pre-written answer key, with real latency, tokens and cost shown. An animation-rich "editorial ledger" UI makes the difference legible to a non-technical audience. This beats a slide deck or a notebook because stakeholders see the behaviour happen live (or from recorded real runs) on documents they can inspect.

## Key Hypothesis

We believe a Jev + code pipeline will produce more correct and traceable audit findings than a single LLM prompt — with an explicit uncertainty signal — at lower cost, for audit/finance decision-makers.
We'll know we're right when, on the S1 and S2 answer keys, Jev's accuracy ≥ the LLM's across 3 runs, Jev's run-to-run variance is 0, Jev's cost per document is lower, and stakeholders approve a pilot.

## What We're NOT Building

- Processing real client data — synthetic documents only (compliance and data-handling risk).
- Authentication / multi-user accounts — single presenter, local run.
- Production audit sign-off — the tool is assistive; findings are illustrative.
- Prose generation with Jev — Jev does not generate text; narrative belongs to the LLM (S3 shows them working together).
- Mobile-first design — presented on projector/video call; layout stays responsive but desktop is primary.
- S4 (expenses at scale), S5 (loan covenant), document upload, working-paper export, hosted deployment — deferred to later phases.

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| Jev accuracy vs. answer key (S1, S2) | ≥ LLM accuracy, 3 runs each | Automated scorecard in the app |
| Jev run-to-run variance | 0 differences in findings across 3 runs | Consistency-run feature |
| Cost per document | Jev pipeline < LLM | Token usage × published prices, shown in app |
| Audience comprehension | Stakeholders can restate the difference in one sentence | Post-demo feedback |
| Business outcome | Go/no-go decision on a Jev pilot | Stakeholder decision after demo |
| Demo reliability | 0 failures during presentation | Replay mode available as fallback |
| API spend | ≤ $5.00 per API key (OpenAI, TypeSafe), lifetime of the project | Persistent spend ledger; app refuses live calls that would exceed the cap |

## Open Questions

- [ ] Demo date? (No deadline yet.)
- [ ] Success threshold if the LLM matches Jev on accuracy — is the traceability/confidence/cost story sufficient?
- [ ] What internal trigger or decision is this demo meant to drive?

---

## Users & Context

**Primary User**
- **Who**: The presenter (project owner) running the demo live on a projector or video call.
- **Current behavior**: Explaining AI options verbally or with slides; no hands-on comparison.
- **Trigger**: An upcoming presentation to the team and business stakeholders.
- **Success state**: Runs every scenario smoothly, the difference is obvious, the audience asks about a pilot.

**Decision-makers (audience)**: Finance and audit leadership. **Secondary**: engineering team (how it works, how to build on it).

**Job to Be Done**
When I present AI options for audit work, I want a side-by-side that shows accuracy, traceability, confidence and cost differences, so leadership can make an evidence-based decision about adopting Jev.

**Non-Users**
Production audit users, external clients, the general public, mobile-first users.

---

## Solution Detail

### Core Capabilities (MoSCoW)

| Priority | Capability | Rationale |
|----------|------------|-----------|
| Must | S1 Contract-to-invoice reconciliation (both sides) | Headline scenario; exposes arithmetic + traceability gap |
| Must | S2 Agreement clause risk review (incl. missing-clause trap) | Shows parallel typed questions + "not present" handling |
| Must | S3 Jev verifies an LLM-written audit memo's citations | "Better together" message; LLM for prose, Jev for verification |
| Must | Answer-key scorecard per scenario | Objective, non-cherry-picked comparison |
| Must | Confidence-gated "Auditor review" lane | Core business differentiator: knows when it doesn't know |
| Must | Live + Replay modes (Replay = recorded real runs, labelled) | Demo reliability |
| Must | Latency / tokens / cost per side | Honest cost-benefit view |
| Must | Budget guard: hard cap of $5.00 per API key | Presenter constraint; pre-flight cost estimate + persistent ledger blocks calls that would exceed the cap; Replay mode for rehearsals |
| Must | Animated side-by-side UI (editorial ledger), reduced-motion support | Requested UX quality; accessibility |
| Should | Consistency run ×3 | Strongest single moment for business audience |
| Should | Click-a-number → highlighted source span | Traceability made visible |
| Could | Choice option-order double-check indicator | Shows mitigation of a known Jev weakness |
| Won't (v1) | S4, S5, document upload, export, hosting, auth | Deferred; not needed to test the hypothesis |

### MVP Scope

S1 only, end-to-end: Live + Replay, side-by-side UI with core animations, scorecard, cost/latency, review lane.

### User Flow

Open app → pick scenario (S1) → view documents → **Run** → both panes animate (LLM streams text; Jev pipeline shows candidates → parallel questions → typed answers → code calculations) → scorecard reveals → low-confidence items glide to review lane → optional **Run ×3** for consistency → next scenario.

---

## Technical Approach

**Feasibility**: HIGH

**Architecture Notes**
- Backend: Python 3.11, FastAPI, `uv`, code in `src/jev/` (per `CLAUDE.md`); `typesafe-sdk` for Jev, official `openai` SDK for the baseline; keys from env (`TYPESAFE_API_KEY`, `OPENAI_API_KEY`), never sent to the browser.
- Frontend: React + TypeScript + Vite + Motion in `web/`; compositor-only animations; `prefers-reduced-motion` respected.
- Jev patterns used (from TypeSafe cookbooks): pre-parsed value extraction (regex candidates → Choice pick with `none` hatch, verbatim copy), parallel questions in one request, line-by-line search for clause location, citation check, confidence-gated routing (threshold starting at 0.8).
- All arithmetic with `Decimal` and all date comparison in code (per Jev 1.13 jaggedness guidance).
- Replay files store recorded real API responses with model ID and timestamp; UI labels them as recorded.
- Answer keys authored by hand alongside synthetic documents before any model runs.
- Budget guard: a persistent spend ledger per provider (git-ignored), pre-flight cost estimates from token counts and published prices, and a hard stop before any call that would push a key past $5.00. Tests never hit live APIs.

**Technical Risks**

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Jev weak spots (numbers, dates, option order, large state) | M | Maths/dates in code; filtered small state; option-order re-check on key Choices |
| Live API/network failure on stage | M | Replay mode from recorded real runs |
| LLM performs well → small accuracy gap | M | Report honestly; traceability, confidence lane and cost still differentiate; answer keys fixed in advance |
| Jev rate limits change without notice | L | Batch questions per request; SDK retries; Replay fallback |
| OpenAI model naming/API drift | L | Model configurable; verify against current docs at plan time |
| Exceeding the $5/key budget | M | Persistent spend ledger per provider; pre-flight estimate and hard stop; default to Replay; Live runs only for recording and final demo; cheap model for development |

---

## Implementation Phases

| # | Phase | Description | Status | Parallel | Depends | PRP Plan |
|---|-------|-------------|--------|----------|---------|----------|
| 1 | Scaffold & quality gates | ECC_SETUP phases 1–6: uv project, FastAPI skeleton, web/ skeleton, settings, hooks, CI | pending | - | - | - |
| 2 | Synthetic data & answer keys | Northwind Logistics agreements, invoices, memo; hand-written answer keys | pending | with 3 | 1 | - |
| 3 | Core engine | Jev client, OpenAI client, replay store, scoring, cost/latency metrics | pending | with 2 | 1 | - |
| 4 | S1 pipeline + API | Reconciliation on both sides, review lane, endpoints | pending | - | 2, 3 | - |
| 5 | UI foundation + S1 screens | Design tokens, layout, core animations, scorecard (MVP complete) | pending | - | 4 | - |
| 6 | S2 + S3 | Clause review and citation verification, backend + UI | pending | - | 5 | - |
| 7 | Polish & rehearsal | Consistency run, source highlighting, recorded replays, a11y/visual checks, run-of-show | pending | - | 6 | - |

### Phase Details

**Phase 1: Scaffold & quality gates** — Goal: a clean, tested skeleton per `ECC_SETUP.md`. Success: `pytest`, `ruff`, `mypy`, web build all pass in CI.

**Phase 2: Synthetic data & answer keys** — Goal: realistic, fictional audit documents with planted, known issues. Success: every scenario has documents + answer key reviewed by the presenter.

**Phase 3: Core engine** — Goal: provider clients, replay, scoring, metrics behind tested interfaces. Success: ≥ 80% coverage; clients mocked in tests.

**Phase 4: S1 pipeline + API** — Goal: reconciliation both ways with review lane. Success: scorecard runs against the S1 answer key via API.

**Phase 5: UI foundation + S1** — Goal: the MVP on screen with signature animations. Success: presenter can run S1 end-to-end in Live and Replay.

**Phase 6: S2 + S3** — Goal: remaining must-have scenarios. Success: all three scenarios scored and animated.

**Phase 7: Polish & rehearsal** — Goal: demo-ready. Success: consistency run, recorded replays, visual checks at key breakpoints, reduced-motion verified, dry run completed.

### Parallelism Notes

Phases 2 and 3 are independent (data vs. engine) and can run concurrently after the scaffold. Everything else is sequential because each phase builds on the previous UI/API surface.

---

## Decisions Log

| Decision | Choice | Alternatives | Rationale |
|----------|--------|--------------|-----------|
| Baseline LLM | OpenAI | Claude, Gemini, Azure OpenAI | Presenter's choice; TypeSafe docs also benchmark against OpenAI |
| Baseline model | `gpt-6-luna` (configurable via env) | `gpt-6-astra`, `gpt-6.1-sol` | Presenter's choice; cheapest current general model ($0.10/$0.50 per 1M tokens, verified on OpenAI models page 2026-10-09); keeps live runs well within the $5 cap |
| Architecture | FastAPI (`src/jev/`) + React/TS/Vite/Motion (`web/`) | All-TS Next.js; all-Python Streamlit | Matches `CLAUDE.md`; best animation capability; keys server-side |
| Role of Jev | Judgments only; code does maths/dates | Ask Jev to compute | Jev 1.13 docs: "not a calculator", dates unreliable |
| Data | Synthetic only (fictional "Northwind Logistics") | Sanitised real docs | Presenter decision; no compliance risk |
| Demo reliability | Live + Replay of recorded real runs | Live only | Avoid stage failures; replays labelled honestly |
| Process | Follow `ECC_SETUP.md` with every ⏸ checkpoint | Condensed | Presenter decision |
| API budget | Hard cap $5.00 per API key, enforced in code | Soft guideline | Presenter constraint; prevents surprise spend |

---

## Research Summary

**Market Context**
Audit AI vendors converge on traceability (DataSnipper links each figure to its source page), anomaly detection over full ledgers (MindBridge), and contract-vs-invoice auditing (AppZen). Regulators (PCAOB) are scrutinising generative-AI use; trust in AI output is falling among practitioners. The winning posture is assistive AI with human review and traceable evidence. Sources: [Trullion](https://trullion.com/blog/ai-hallucination-in-accounting-and-audit/), [idp-software](https://idp-software.com/vendors/datasnipper/), [pymnts](https://pymnts.com/?p=616268), [StackAI](https://www.stackai.com/blog/the-top-ai-agent-use-cases-for-accounting-audit-in-2026).

**Technical Context**
Jev (`jev-latest` → `jev-1.13.0`): state + typed questions → typed answers with calibrated probabilities/confidence; questions evaluated in parallel; $0.042/M input tokens, output free; 64k context (32k state + longest question); Python `typesafe-sdk` and JS `@typesafe-ai/sdk`; known weak spots in arithmetic, counting, dates, indirection, large irrelevant state and option order. Greenfield repo; conventions from `CLAUDE.md` (strict mypy, ≥ 80% coverage, frozen dataclasses, `src/jev/`).

---

*Generated: 2026-10-09*
*Status: DRAFT — needs validation*
