"""Command-line tools.

uv run python -m jev.cli data validate
uv run python -m jev.cli budget init
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from jev.budget.ledger import Ledger
from jev.config import Settings
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

    args = parser.parse_args(argv)
    if args.group == "budget":
        return _budget_init(args.ledger_path)
    return _validate(args.data_dir)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
