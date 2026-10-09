"""Append-only JSONL spend ledger, locked for read-modify-write and failing closed.

Entries never contain an API key, only its fingerprint. Kinds:
reserve (worst-case estimate before a call), commit (actual cost; closes a reservation),
release (call never sent; closes a reservation), adjust (manual spend made elsewhere).

The ledger must be created explicitly (`jev.cli budget init`). A missing ledger is refused
rather than silently recreated, so moving or deleting it can't reset the lifetime cap.
"""

import fcntl
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import IO, Literal, get_args

EntryKind = Literal["reserve", "commit", "release", "adjust"]
Provider = Literal["openai", "typesafe"]
_KINDS = frozenset(get_args(EntryKind))
_PROVIDERS = frozenset(get_args(Provider))
_PRIVATE_FILE_MODE = 0o600


class LedgerCorruptError(RuntimeError):
    """The ledger can't be trusted, so no live call may proceed (fail closed)."""


class LedgerMissingError(RuntimeError):
    """No ledger exists at the configured path; refuse instead of starting a fresh budget."""


@dataclass(frozen=True)
class LedgerEntry:
    ts: str
    provider: Provider
    key_fp: str
    kind: EntryKind
    usd: str  # Decimal as string
    id: str  # reservation id (shared by reserve and its commit/release)
    run_id: str = ""
    note: str = ""

    @property
    def amount(self) -> Decimal:
        return Decimal(self.usd)


def _valid_amount(kind: str, amount: Decimal) -> bool:
    if not amount.is_finite():
        return False
    return amount > 0 if kind in ("reserve", "adjust") else amount >= 0


def _parse_line(line_no: int, raw: str) -> LedgerEntry:
    try:
        entry = LedgerEntry(**json.loads(raw))
        valid = (
            isinstance(entry.kind, str)
            and isinstance(entry.provider, str)
            and isinstance(entry.usd, str)
            and entry.kind in _KINDS
            and entry.provider in _PROVIDERS
            and _valid_amount(entry.kind, Decimal(entry.usd))
        )
    except (json.JSONDecodeError, TypeError, InvalidOperation) as exc:
        raise LedgerCorruptError(f"Ledger line {line_no} is unreadable") from exc
    if not valid:
        raise LedgerCorruptError(f"Ledger line {line_no} has an invalid kind, provider or amount")
    return entry


class LedgerSession:
    """A locked view of the ledger: read every entry, then append atomically."""

    def __init__(self, handle: IO[str]) -> None:
        self._handle = handle
        handle.seek(0)
        try:
            lines = handle.read().splitlines()
        except UnicodeDecodeError as exc:
            raise LedgerCorruptError("Ledger is not valid UTF-8") from exc
        self.entries: tuple[LedgerEntry, ...] = tuple(
            _parse_line(n, line) for n, line in enumerate(lines, 1) if line.strip()
        )

    def append(self, entry: LedgerEntry) -> None:
        self._handle.seek(0, os.SEEK_END)
        self._handle.write(json.dumps(asdict(entry), sort_keys=True) + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self.entries = (*self.entries, entry)


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialise(self) -> None:
        """Create an empty, owner-only ledger. Refuses to overwrite an existing one."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, _PRIVATE_FILE_MODE)
        os.close(fd)

    @contextmanager
    def session(self) -> Iterator[LedgerSession]:
        """Exclusive lock across processes for the whole read-check-append sequence."""
        if not self.path.is_file():
            raise LedgerMissingError(
                f"No spend ledger at {self.path}. Create it once with "
                "`uv run python -m jev.cli budget init`; it is never recreated automatically."
            )
        with self.path.open("r+", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield LedgerSession(handle)
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
