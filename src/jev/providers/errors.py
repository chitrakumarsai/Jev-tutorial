"""Provider failures, reduced to messages that are safe to show (no keys, no bodies)."""

from typing import Literal

ProviderName = Literal["typesafe", "openai"]


class ProviderError(RuntimeError):
    def __init__(self, provider: ProviderName, message: str) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider: ProviderName = provider
