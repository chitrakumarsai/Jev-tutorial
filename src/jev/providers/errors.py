"""Provider failures, reduced to messages that are safe to show (no keys, no bodies)."""

import re
from typing import Literal

ProviderName = Literal["typesafe", "openai"]

_SAFE_TOKEN = re.compile(r"[A-Za-z0-9_.\-]{1,64}")


class ProviderError(RuntimeError):
    def __init__(self, provider: ProviderName, message: str) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider: ProviderName = provider


def safe_failure(exc: BaseException, **fields: object) -> str:
    """`ExcClass, HTTP 404, code=model_not_found`: the class plus only identifier-like fields
    (status, error code, param, request id), so the reason shows but body text never does."""
    parts = [type(exc).__name__]
    status = fields.get("status")
    if isinstance(status, int):
        parts.append(f"HTTP {status}")
    for name, value in fields.items():
        if name != "status" and isinstance(value, str) and _SAFE_TOKEN.fullmatch(value):
            parts.append(f"{name}={value}")
    return ", ".join(parts)
