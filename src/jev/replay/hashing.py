"""Canonical request hashing: identical requests hash identically regardless of key order."""

import hashlib
import json

from pydantic import JsonValue


def request_hash(payload: JsonValue) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
