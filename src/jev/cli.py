"""Command-line tools.

uv run python -m jev.cli data validate
uv run python -m jev.cli budget init
"""

import argparse
import asyncio
import sys
import uuid
from collections.abc import Callable, Sequence
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from jev.budget.guard import BudgetExceededError
from jev.budget.ledger import Ledger, LedgerCorruptError, LedgerMissingError
from jev.budget.pricing import UnknownModelError
from jev.config import Settings
from jev.providers.factory import LiveDisabledError, MissingKeyError
from jev.runs.service import PreparedLive, RunService
from jev.scenarios.s1_reconciliation.documents import DocumentTooLargeError, validate_s1_data

DEFAULT_DATA_DIR = Path("data")


def _validate(data_dir: Path) -> int:
    try:
        problems = validate_s1_data(data_dir)
    except ValidationError as exc:
        print(f"Answer key is invalid: {exc.error_count()} error(s)\n{exc}", file=sys.stderr)
        return 1
    except (DocumentTooLargeError, FileNotFoundError) as exc:
        print(f"Documents are invalid: {exc}", file=sys.stderr)
        return 1
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print("OK: S1 documents and answer key are consistent.")
    return 0


def _budget_init(ledger_path: Path | None) -> int:
    path = ledger_path or Settings().ledger_path
    try:
        Ledger(path).initialise()
    except FileExistsError:
        print(f"A spend ledger already exists at {path}; it is never reset.", file=sys.stderr)
        return 1
    print(f"Created an empty spend ledger at {path}.")
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
        except Exception as exc:  # the class only: provider messages can carry request text
            print(
                f"Run {n}/{runs} failed ({type(exc).__name__}); money may have been spent. "
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jev.cli", description="Jev Audit Lens tools")
    groups = parser.add_subparsers(dest="group", required=True)
    data = groups.add_parser("data", help="synthetic data checks")
    data_cmds = data.add_subparsers(dest="command", required=True)
    validate = data_cmds.add_parser("validate", help="check documents against the answer key")
    validate.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)

    budget = groups.add_parser("budget", help="API spend ledger")
    budget_cmds = budget.add_subparsers(dest="command", required=True)
    init = budget_cmds.add_parser("init", help="create the spend ledger (once)")
    init.add_argument("--ledger-path", type=Path, default=None)

    rec = groups.add_parser("record", help="LIVE: record real runs for replay (spends money)")
    rec.add_argument("scenario", choices=["s1"])
    rec.add_argument("--runs", type=_runs_arg, default=1)

    args = parser.parse_args(argv)
    if args.group == "record":  # pragma: no cover - interactive, exercised via record()
        return record(RunService(Settings()), runs=args.runs)
    if args.group == "budget":
        return _budget_init(args.ledger_path)
    return _validate(args.data_dir)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
