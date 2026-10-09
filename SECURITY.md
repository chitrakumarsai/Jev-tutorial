# Security Policy

Jev Audit Lens is an internal demo that runs on **synthetic data only**. Do not load real client documents.

## Secrets

- API keys (`TYPESAFE_API_KEY`, `OPENAI_API_KEY`) live only in `.env`, which is git-ignored (as are `.env.*` except `.env.example`, `*.pem` and `*.key`). `.env.example` lists the variables with no values.
- Keys are read as `SecretStr` (`src/jev/config.py`), never logged, and never included in error messages (provider errors report only the exception type). The spend ledger stores only a SHA-256 fingerprint of each key.
- Claude Code guardrails, defence in depth rather than a sandbox:
  - `scripts/hooks/pre_tool_guard.sh` denies file, search and shell access to dotenv files and environment dumps, and fails closed if it can't parse a tool call. It is pattern-based, so a determined obfuscated command could slip past it; the `permissions.deny` list is a second layer. Tests: `tests/hooks/test_pre_tool_guard.py`.
  - Edits to the harness itself (`.claude/`, `scripts/hooks/`, CI, tool configs) require the user's approval.

## Spend limits

- Live API calls are off by default (`LIVE_ENABLED=false`); live clients can only be built through `src/jev/providers/factory.py`, which refuses unless live mode is on and both keys are set.
- A hard cap of **$5.00 per API key** is enforced in code before every call (`src/jev/budget/`): a locked, append-only ledger that must be created explicitly (`jev.cli budget init`), a pre-call reservation of the worst-case cost, fail-closed on any corrupt entry, and a $0.25 safety margin. This is the real control; the guard hook additionally asks before commands that enable live mode or call the provider APIs.
- OpenAI calls set `store=False`, so audit documents are not kept in OpenAI's stored responses.
- CI has no keys.

## Network exposure

- Planned (task P7): the API binds to `127.0.0.1`, allows CORS only from the local Vite dev origin, and uses trusted-host checks against DNS rebinding.

## Reporting a vulnerability

Open a private security advisory on the GitHub repository or contact the maintainer directly. Please do not open a public issue for security problems.
