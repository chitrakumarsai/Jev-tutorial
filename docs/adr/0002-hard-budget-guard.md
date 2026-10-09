# ADR 0002: Hard $5 budget per API key, enforced in code

- **Status:** Accepted (2026-10-09)
- **Context:** The presenter set a hard limit of $5.00 lifetime spend per API key (OpenAI and TypeSafe).
- **Decision:** A persistent, git-ignored JSONL ledger per provider (keyed by a SHA-256 fingerprint of the key), a whole-run pre-flight estimate, and per-call reserve → call → commit-actual. It fails closed on a corrupt ledger or unknown model price. Live mode is off by default, Replay is the default mode, recording is CLI-only, and the Claude Code guard hook asks before any live command. The cap can be lowered via env but never raised above 5.00.
- **Consequences:** Estimates are pessimistic, so some headroom is left unused. Tests and CI can never spend.
