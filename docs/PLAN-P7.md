# Jev Audit Lens — Phase 7 Plan (Polish & rehearsal)

> Source: [PRD.md](PRD.md) Phase 7 ("demo-ready: consistency run, recorded replays, visual checks at key breakpoints, reduced-motion verified, dry run completed") and the PRD flow's "optional **Run ×3** for consistency". Builds on Milestones 1–2 (S1–S3 recorded, 3 runs each).
> Drafted 2026-10-12. **Status: approved by the presenter 2026-10-12** (decisions in §3 accepted as recommended).

## 1. Already done (no work)

- Recorded replays: S1, S2, S3 each have 3 separate live recordings, with golden tests.
- Visual check foundations: full-page screenshots at 320 / 768 / 1024 / 1440 in both themes (S1), plus a per-scenario scorecard screenshot (#34). Axe, reduced motion and keyboard checks pass for S1.

## 2. Tasks

| ID | Task | Gate | Size |
|---|---|---|---|
| **P7-1** | **Consistency ×3, backend.** `GET /api/scenarios/{id}/consistency` replays the scenario's three recordings without pacing. There is no live call and no spend. It returns, for each key item and each side, the outcome of each run (verdict or variance plus status), and flags any item whose outcome differs between runs. Each recording is labelled with its date and model. | pytest: S1–S3 report 0 differences for Jev; S3 shows the LLM's C5 difference | M |
| **P7-2** | **Consistency ×3, UI.** A "Consistency ×3" button next to Replay opens a panel below the Results. For each side it shows a grid of items × 3 runs, with differences highlighted (with a symbol, not colour alone) and a summary such as "Jev: same answer on all 10 items in 3 runs · LLM: 1 item changed (C5)". Motion: a short stagger, with reduced motion respected. | RTL + E2E for all 3 scenarios, axe | M |
| **P7-3** | **S2 and S3 visual and accessibility checks.** Run axe in both themes, before and after a run, for S2 and S3, plus the reduced-motion recorder and full-page screenshots at the 4 widths for S2 and S3 results. Verify that S2's line highlights and S3's citation evidence highlights land on the right spans. | E2E green | M |
| **P7-4** | **Memo citation links (S3).** In the Memo tab, each `[Cn]` marker becomes a button that scrolls to and highlights that citation's ledger rows on both sides. It is keyboard accessible. | RTL + E2E | S |
| **P7-5** | **`jev.cli budget show`.** Prints spent / cap / headroom per provider from the ledger. It is read-only, with no keys printed. Used in the pre-demo checklist. | pytest | S |
| **P7-6** | **Run-of-show** (`docs/RUN-OF-SHOW.md`). A pre-demo checklist (main green, `budget show`, Replay default, browser zoom, theme), a talk track per scenario (S1 → S2 → S3, about 15 minutes, with the one-sentence takeaway for each), when to use Consistency ×3, Live-run steps if wanted (LIVE_ENABLED, cost shown first), and fallbacks (Replay; what to say if Live refuses or a provider errors). | Presenter review | S |
| **P7-7** | **Dry run.** I run the run-of-show end to end in Replay and capture screenshots of each step into the doc. The presenter rehearses and notes changes; I apply them. | Presenter sign-off | S |

Order: P7-5 and P7-1 → P7-2 → P7-3 and P7-4 → P7-6 → P7-7. Each is a PR with reviewers, as before.

## 3. Decisions (accepted by presenter, 2026-10-12)

1. **What "Consistency ×3" runs.** Recommended: **replay the 3 existing separate recordings**, which costs nothing, is deterministic, and is labelled "3 recorded live runs". The alternative is 3 live runs from the UI (about $0.01–0.03 per scenario, needs Live on and a confirmation). Replaying one recording three times would be trivially identical, so it is excluded, as in PLAN.md.
2. **Where it shows.** Recommended: a panel below the Results, opened by a "Consistency ×3" button. The alternative is a separate view.
3. **Demo length and order.** Recommended: S1 → S2 → S3, about 15 minutes, with Consistency ×3 shown on S3, where the LLM's answer changes.

## 4. Risks

| Risk | Mitigation |
|---|---|
| The 3 recordings per scenario don't show LLM variance on S1 or S2 | Report it honestly; S3 shows it. More runs only with presenter approval (`record --runs`) |
| Screenshot baselines are macOS-only | Unchanged policy; CI runs every other assertion |
| Context and cost of long sessions | One PR per task; save and resume between tasks |
