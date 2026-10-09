# ADR 0001: Jev makes judgments; code does all maths and dates

- **Status:** Accepted (2026-10-09)
- **Context:** TypeSafe's own "Jev 1.13 jaggedness" page says Jev is not a calculator, does not count reliably, and is unreliable at comparing dates. It returns typed answers (Choice / Score / Noul) with calibrated confidence and does not generate text.
- **Decision:** Code finds candidate values with regexes and performs every calculation with `Decimal` (and every date comparison) itself. Jev only picks among candidate spans found in the documents (always with a `none` option), classifies, and checks statements. Findings below 0.8 confidence go to an auditor review lane.
- **Consequences:** Every reported value is a verbatim copy of a document span, so it can't be invented. More code than a single LLM prompt, which is the point of the demo. Narrative text (if ever needed) belongs to an LLM, not Jev.
