"""Command-line tools.

uv run python -m jev.cli data validate [--scenario ID]
uv run python -m jev.cli record s1 --runs 3   # LIVE: spends money, asks for confirmation
uv run python -m jev.cli draft-memo           # LIVE: one call drafts the S3 memo (D6)
uv run python -m jev.cli budget init
uv run python -m jev.cli openapi   # refresh web/openapi.json for the web client
"""

import argparse
import asyncio
import json
import sys
import uuid
from collections.abc import Callable, Sequence
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from jev.budget.guard import BudgetExceededError
from jev.budget.ledger import Ledger, LedgerCorruptError, LedgerMissingError
from jev.budget.pricing import UnknownModelError
from jev.budget.report import budget_report
from jev.config import Settings
from jev.providers.errors import ProviderError
from jev.providers.factory import (
    LiveDisabledError,
    MissingKeyError,
    build_guard,
    build_live_clients,
)
from jev.runs.service import PreparedLive, RunService
from jev.scenarios.registry import SCENARIOS, ScenarioSpec, get_scenario
from jev.scenarios.s1_reconciliation.documents import DocumentTooLargeError, load_s1_documents
from jev.scenarios.s3_citation_check.memo_draft import draft_memo

DEFAULT_DATA_DIR = Path("data")
DEFAULT_OPENAPI_OUT = Path("web/openapi.json")


def scenario_arg(name: str) -> ScenarioSpec:
    """A scenario by full id ("s1_reconciliation") or short alias ("s1")."""
    spec = get_scenario(name)
    if spec is None:
        known = ", ".join(s.id for s in SCENARIOS)
        raise argparse.ArgumentTypeError(f"unknown scenario {name!r} (known: {known})")
    return spec


def _validate_one(spec: ScenarioSpec, data_dir: Path) -> int:
    try:
        problems = spec.validate_data(data_dir)
    except ValidationError as exc:
        print(
            f"{spec.id}: Answer key is invalid: {exc.error_count()} error(s)\n{exc}",
            file=sys.stderr,
        )
        return 1
    except (DocumentTooLargeError, FileNotFoundError) as exc:
        print(f"{spec.id}: Documents are invalid: {exc}", file=sys.stderr)
        return 1
    if problems:
        print("\n".join(f"{spec.id}: {p}" for p in problems), file=sys.stderr)
        return 1
    print(f"OK: {spec.id} documents and answer key are consistent.")
    return 0


def _validate(data_dir: Path, only: ScenarioSpec | None) -> int:
    specs = (only,) if only else SCENARIOS
    return max(_validate_one(spec, data_dir) for spec in specs)


def _budget_init(ledger_path: Path | None) -> int:
    path = ledger_path or Settings().ledger_path
    try:
        Ledger(path).initialise()
    except FileExistsError:
        print(f"A spend ledger already exists at {path}; it is never reset.", file=sys.stderr)
        return 1
    print(f"Created an empty spend ledger at {path}.")
    return 0


def _budget_show() -> int:
    """Spent / cap / headroom per provider. Read-only: never creates the ledger, never
    prints a key or its fingerprint."""
    try:
        initialised, rows = budget_report(Settings())
    except LedgerCorruptError as exc:  # its message names a line number, never content
        print(f"The spend ledger is corrupt ({exc}); live calls are refused.", file=sys.stderr)
        return 1
    except (OSError, ValidationError) as exc:
        print(f"Cannot read the budget ({type(exc).__name__}).", file=sys.stderr)
        return 1
    if not initialised:
        print("No spend ledger yet; create it once with `budget init`.", file=sys.stderr)
        return 1
    for row in rows:
        if not row.key_configured or row.spent is None:
            print(f"{row.provider}: no key configured (cap ${row.cap:.2f})")
            continue
        print(
            f"{row.provider}: spent ${row.spent:.4f} of ${row.cap:.2f}, "
            f"reserved ${row.reserved or 0:.4f}, remaining ${row.remaining or 0:.4f}"
        )
    return 0


def openapi_json() -> str:
    """The API spec as stable, diff-friendly JSON (the web client is generated from it)."""
    from jev.api.app import create_app  # local: the other commands don't need the web app

    return json.dumps(create_app().openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _openapi(out: Path) -> int:
    out.write_text(openapi_json(), encoding="utf-8")
    print(f"Wrote {out}.")
    return 0


MAX_RECORD_RUNS = 5
CONFIRM_WORD = "RECORD"
_REFUSALS = (
    LiveDisabledError,
    MissingKeyError,
    BudgetExceededError,
    LedgerMissingError,
    LedgerCorruptError,
    UnknownModelError,
)


def _runs_arg(value: str) -> int:
    runs = int(value)
    if not 1 <= runs <= MAX_RECORD_RUNS:
        raise argparse.ArgumentTypeError(f"must be between 1 and {MAX_RECORD_RUNS}")
    return runs


def _confirmed(prepared: PreparedLive, runs: int, input_fn: Callable[[str], str]) -> bool:
    """Show the per-run and total worst case; spend only on the exact confirmation word."""
    costs = ", ".join(f"{p} ${amount:.4f}" for p, amount in sorted(prepared.estimates.items()))
    total = runs * sum(prepared.estimates.values(), Decimal("0"))
    try:
        answer = input_fn(
            f"Recording {runs} live run(s). Per run, worst case: {costs}; "
            f"total worst case ${total:.4f} (capped at the configured limit per key). "
            f"Type {CONFIRM_WORD} to spend: "
        )
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer.strip() == CONFIRM_WORD:
        return True
    asyncio.run(prepared.clients.aclose())
    print("Cancelled; nothing was sent.", file=sys.stderr)
    return False


def record(service: RunService, *, runs: int, input_fn: Callable[[str], str] = input) -> int:
    """Record live runs for replay. Shows the worst-case cost and needs a typed confirmation."""
    if not 1 <= runs <= MAX_RECORD_RUNS:
        raise ValueError(f"runs must be between 1 and {MAX_RECORD_RUNS}")
    for n in range(1, runs + 1):
        try:
            prepared = service.prepare_live(f"rec-{uuid.uuid4().hex[:8]}")
        except _REFUSALS as exc:
            print(f"Refused: {exc}", file=sys.stderr)
            return 1
        if n == 1 and not _confirmed(prepared, runs, input_fn):
            return 1
        try:
            result = asyncio.run(service.run_prepared(prepared, lambda event: None))
        except Exception as exc:  # provider messages are sanitised; others show the class only
            reason = str(exc) if isinstance(exc, ProviderError) else type(exc).__name__
            print(
                f"Run {n}/{runs} failed ({reason}); money may have been spent. "
                "Check `budget` before retrying.",
                file=sys.stderr,
            )
            return 1
        jev, llm = result.sides["jev"].scorecard, result.sides["llm"].scorecard
        print(
            f"Run {n}/{runs}: Jev {jev.correct}/{jev.of} (+{jev.correct_in_review} in review), "
            f"LLM {llm.correct}/{llm.of}. Recorded as {result.recording_id}."
        )
    return 0


DEFAULT_MEMO_DIR = DEFAULT_DATA_DIR / "scenarios" / "s3_citation_check"


class _LlmOnly:
    """The live OpenAI client for the draft, closing both live clients when done."""

    def __init__(self, clients: Any) -> None:
        self._clients = clients
        self.key_fp = clients.llm.key_fp
        self.estimate = clients.llm.estimate
        self.parse = clients.llm.parse

    async def aclose(self) -> None:
        await self._clients.aclose()


def _draft_memo(data_dir: Path, out_dir: Path) -> int:
    settings = Settings()
    guard = build_guard(settings)
    try:
        clients = build_live_clients(settings, guard)
        return draft_memo(
            load_s1_documents(data_dir),
            out_dir,
            llm_factory=lambda: _LlmOnly(clients),
            guard=guard,
        )
    except _REFUSALS as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jev.cli", description="Jev Audit Lens tools")
    groups = parser.add_subparsers(dest="group", required=True)
    data = groups.add_parser("data", help="synthetic data checks")
    data_cmds = data.add_subparsers(dest="command", required=True)
    validate = data_cmds.add_parser("validate", help="check documents against the answer key")
    validate.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    validate.add_argument("--scenario", type=scenario_arg, default=None, help="default: all")

    budget = groups.add_parser("budget", help="API spend ledger")
    budget_cmds = budget.add_subparsers(dest="command", required=True)
    init = budget_cmds.add_parser("init", help="create the spend ledger (once)")
    init.add_argument("--ledger-path", type=Path, default=None)
    budget_cmds.add_parser("show", help="spent / cap / headroom per provider (read-only)")

    rec = groups.add_parser("record", help="LIVE: record real runs for replay (spends money)")
    rec.add_argument("scenario", type=scenario_arg, help="id or short alias, e.g. s1")
    rec.add_argument("--runs", type=_runs_arg, default=1)

    memo = groups.add_parser("draft-memo", help="LIVE: draft the S3 memo once (spends money)")
    memo.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    memo.add_argument("--out-dir", type=Path, default=DEFAULT_MEMO_DIR)

    spec = groups.add_parser("openapi", help="export the API spec for the web client")
    spec.add_argument("--out", type=Path, default=DEFAULT_OPENAPI_OUT)

    args = parser.parse_args(argv)
    if args.group == "record":  # pragma: no cover - interactive, exercised via record()
        return record(RunService(Settings(), scenario=args.scenario), runs=args.runs)
    if args.group == "draft-memo":
        return _draft_memo(args.data_dir, args.out_dir)
    if args.group == "budget":
        if args.command == "show":
            return _budget_show()
        if args.command == "init":
            return _budget_init(args.ledger_path)
    if args.group == "openapi":
        return _openapi(args.out)
    return _validate(args.data_dir, args.scenario)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
