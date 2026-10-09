# ADR 0003: Replay mode re-runs the real pipeline over recorded real responses

- **Status:** Accepted (2026-10-09)
- **Context:** Live demos can fail on bad networks or rate limits, and rehearsals must not spend budget. Showing fabricated output would undermine the demo's credibility.
- **Decision:** Replay swaps the provider clients for ones that serve **recorded results of real API calls**: our typed `JevResult` / `LlmResult` exactly as returned by the live adapters (with model ID, latency and timestamp; never headers or keys), keyed by a SHA-256 hash of the canonical request. The real pipeline code runs unchanged. A missing recording fails loudly (`REPLAY_STALE`) and never falls back to a live call. The UI labels replays as "Recorded {date} · {model}". A ×3 consistency demo uses three separate live recordings.
- **Consequences:** Pipeline or prompt changes invalidate recordings, which must be re-recorded (cheap: about $0.003 per S1 run). Recordings double as golden regression tests.
