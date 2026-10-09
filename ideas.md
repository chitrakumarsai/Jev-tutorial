# Jev vs. Plain LLM: Audit Demo Ideas

> **Status:** concept, revised after reading the TypeSafe docs (docs.typesafe.ai, read 2026-10-09).
> Nothing is implemented yet.

---

## 1. What Jev actually is (from the docs, not assumed)

- **Jev** is TypeSafe's flagship model and the first **System One** model (`jev-latest` → `jev-1.13.0`).
- It **does not generate text**. You send a **state** (text / JSON) plus a set of typed **questions**; it returns typed answers:

| Primitive | Asks | Returns |
|---|---|---|
| **Choice** | Pick one option from a set (≤ 255 options) | `choice`, `probabilities`, `confidence` |
| **Score** | Rate on an ordered rubric (2–10 levels) | `score`, `probabilities`, `confidence` |
| **Noul** | Is this statement true? | `noul` (0–1 probability) |

- All questions in one request are evaluated **in parallel and independently** against the same state. Adding questions barely changes latency, and they don't create context rot between each other.
- Probabilities are **calibrated** (trained with RLCD), and **confidence** tells your code *whether to act* or escalate to a human.
- **Price:** $0.042 per million *input* tokens; output is free. Rate limits are 100K tok/s and 80 req/s, and are "adjusting dynamically". Context is 64k per request (32k for state + longest question).
- **SDKs:** Python `typesafe-sdk` (sync + async) and JS/TS `@typesafe-ai/sdk` (Node ≥ 20). Both read `TYPESAFE_API_KEY`. The HTTP endpoint is `POST https://api.typesafe.ai/v1/systemone`.
- **Data:** TypeSafe doesn't train on customer requests. Zero data retention (ZDR) is available for enterprise customers.

### Known weak spots (TypeSafe's own "jaggedness" page for jev-1.13), which the design must respect
1. **Not a calculator**: counting and arithmetic belong in code.
2. **Dates**: extract the parts with Choice questions, then compare and compute in code.
3. Literal reading: write exact conditions and boundary cases in the criteria.
4. Large, irrelevant state hurts accuracy: filter first and send only what's needed.
5. Choice option order can bias the answer: reorder to double-check.
6. No text generation: use an LLM for prose.
7. Adversarial content in the state can steer answers.

**This corrects my earlier `ideas.md`.** Jev does *not* do the calculations. The honest story is:

> **Plain LLM:** one model reads, extracts, calculates and judges, all in free text.
> **Jev pipeline:** *code* finds candidates and does every calculation; *Jev* makes the small judgments (which value is the rate? is this clause present? how risky is it?) with calibrated confidence; *low-confidence items go to a human*.

## 2. The pitch

> **"An LLM gives you a confident paragraph. Jev gives your audit software typed decisions with calibrated confidence, so the maths is exact, every number is copied verbatim from the document, and uncertain items are routed to an auditor instead of guessed."**

What the audience should see, side by side:

| Audit need | Plain LLM (single prompt) | Jev + code pipeline |
|---|---|---|
| Exact arithmetic | Model does the maths; can drift | `Decimal` maths in code; ties to the cent |
| Values traceable to the source | May paraphrase or mistype a number | Jev only **picks among spans found in the document**, so it can't invent a digit |
| Knowing when it doesn't know | Rarely says so | Confidence below threshold → **"Needs auditor review"** lane |
| Missing clause / trap question | May describe a "typical" clause | Noul ≈ 0 → "not present", plus a `none` option on every Choice |
| Same answer every run | Wording and sometimes numbers vary | Typed answers; we demonstrate stability across runs |
| Cost and speed per document | Larger output-token bill and latency | Input-only pricing, many questions in one call |

**Fairness rules for the demo**, so it holds up in front of the business:
- The LLM side gets a well-written prompt with structured (JSON) output. No strawman.
- Both sides see the same documents. We show the real latency, tokens and cost of each.
- We show one case where the LLM does fine, and say where an LLM is the *right* tool (writing the narrative memo).

---

## 3. Scenarios (audit domain, fictional company "Northwind Logistics")

### S1 ⭐ Contract-to-invoice reconciliation (headline)
- **Documents:** a master services agreement (rate card, volume discount tier, fuel surcharge cap, late-fee clause) plus 12 monthly invoices.
- **Jev pipeline:**
  1. Regex finds candidate amounts, rates and dates.
  2. Jev Choice questions pick *which* amount is the unit rate, the discount threshold, the surcharge cap, etc., with a `none` escape hatch.
  3. Date parts are extracted as Choices, then assembled and compared in code.
  4. Code recomputes every invoice line with `Decimal`.
  5. Confidence below 0.8 sends the item to review.
- **Plain LLM:** "Here are the agreement and invoices; list every billing discrepancy with amounts (JSON)."
- **Answer key:** e.g. 3 planted discrepancies (discount not applied from month 7, surcharge over the cap in month 4, a duplicate line in month 10), with an exact total variance.

### S2 ⭐ Agreement clause risk review
- **Documents:** 4–5 vendor agreements.
- **Jev pipeline:** one request per agreement with many questions in parallel:
  - **Nouls:** auto-renewal present? Liability cap present? Termination for convenience? Change-of-control? Audit-rights clause?
  - **Choice:** governing law.
  - **Score:** severity of the indemnity terms on a 4-level rubric.
  - The line-by-line search pattern locates the exact clause line, giving a clickable citation.
- **Plain LLM:** "Summarise the risks in each agreement."
- **Trap built in:** one agreement has *no* audit-rights clause. Does the LLM invent one?

### S3 ⭐ "Better together": Jev verifies the LLM's audit memo
- An LLM drafts an audit-findings memo with citations (this is what LLMs are good at).
- Jev checks every citation, following TypeSafe's citation-check recipe: **verified / unsupported / contradicted / fabricated**, with confidence.
- **Business message:** "Keep your LLM; put Jev in front of it as a cheap, fast verifier."

### S4 Expense-policy compliance at scale
- 500 expense lines plus a travel policy.
- Jev classifies each line (category Choice, policy-violation Nouls). Code applies the limits and sums the exposure.
- Shows **cost and time per 1,000 lines** for Jev vs. the LLM: the map-reduce story.

### S5 Loan covenant check
- Jev extracts which figures are EBITDA, total debt and the covenant threshold, using the candidate-picking method. Code computes the ratio and flags a breach or near-breach.

### Demo "moments" to sprinkle in
- **Consistency run ×3:** the same input three times on each side. The LLM's totals or wording drift; Jev's typed answers and code totals don't.
- **Confidence lane:** watch low-confidence items slide into an "Auditor review" column.
- **Cost meter:** a live counter of $ and ms per side.

---

## 4. Experience & visual direction (you asked for animation-rich, appealing UI)

**Direction: "Editorial ledger".** It mixes the calm of a financial report with precise, purposeful motion.

- **Palette** (semantic, not decorative):
  - Ink navy `#0F1B2D` (surfaces, dark mode) / Paper ivory `#F7F3EA` (light mode)
  - **Verified** teal-green, **Needs review** amber, **Discrepancy** vermilion, **Jev accent** electric indigo, **LLM accent** muted slate
  - Subtle paper-grain texture and a hairline ledger grid in the background
- **Type:** a characterful serif for headlines and big figures (e.g. *Fraunces*), and a clean grotesk with tabular numerals for data (e.g. *Inter* or *IBM Plex Sans*). Two families max.
- **Signature animations** (Motion / Framer Motion, compositor-only, respecting `prefers-reduced-motion`):
  1. **Pipeline flow:** the document → candidate spans highlight in the text → question chips fan out in parallel → answers snap back as typed cards.
  2. **Probability bars** grow in, with the winning option glowing; a **confidence ring** fills.
  3. **Verbatim trace:** clicking a number draws a line to its highlighted span in the source document.
  4. **Ledger tick-off:** reconciliation rows tick off one by one; discrepancies shake slightly and turn vermilion; the total variance counts up.
  5. **Review lane:** low-confidence cards physically glide into the "Auditor review" column.
  6. **Scorecard reveal:** green/red checks against the answer key cascade in, then a final "X/Y correct" badge.
  7. **LLM side:** text streams in like a typewriter, to contrast with Jev's instant structured snap.
- **Modes:** *Live* (real API calls) and *Replay* (recorded real runs, clearly labelled) so the demo never dies on bad Wi-Fi.

---

## 5. Architecture options (decision needed, see questions)

`CLAUDE.md` says **Python 3.11 + uv, code in `src/jev/`**. Jev has both a Python and a TypeScript SDK.

- **Option A (recommended):** Python **FastAPI** backend in `src/jev/` (audit pipelines, Jev and LLM clients, scoring; follows `CLAUDE.md` and ECC Python rules) plus a **React + TypeScript + Vite + Motion** frontend in `web/` for the animated UI. API keys stay server-side.
- **Option B:** all TypeScript (Next.js + `@typesafe-ai/sdk`). One language, but it diverges from `CLAUDE.md`.
- **Option C:** all Python (Streamlit/Reflex). Simplest, but weakest for the animations you want.

## 6. Open questions
1. **Baseline LLM provider:** which model represents the "regular LLM" (Claude, OpenAI, Gemini, Azure OpenAI)? Are API keys available?
2. **TypeSafe API key:** do we have `TYPESAFE_API_KEY` (console.typesafe.ai)?
3. **Architecture:** A, B or C above?
4. **Process:** follow `ECC_SETUP.md` phase by phase with ⏸ checkpoints, or one combined PRD + plan approval and then build?
5. **Scenarios for v1:** I suggest S1 + S2 + S3, plus the three "moments".
