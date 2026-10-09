"""The only place live (paid) clients are built: refuses unless live mode is explicitly on."""

from dataclasses import dataclass

from jev.budget.guard import BudgetGuard
from jev.budget.ledger import Ledger
from jev.config import Settings
from jev.providers.jev.live import LiveJevClient
from jev.providers.openai.live import LiveOpenAIClient


class LiveDisabledError(RuntimeError):
    """Live mode is off; use Replay or explicitly set LIVE_ENABLED=true."""


class MissingKeyError(RuntimeError):
    """A required API key is not configured (its value is never included in messages)."""


@dataclass(frozen=True)
class LiveClients:
    jev: LiveJevClient
    llm: LiveOpenAIClient

    async def aclose(self) -> None:
        await self.jev.aclose()
        await self.llm.aclose()


def build_guard(settings: Settings) -> BudgetGuard:
    return BudgetGuard(Ledger(settings.ledger_path), cap=settings.budget_cap_usd)


def build_live_clients(settings: Settings, guard: BudgetGuard) -> LiveClients:
    if not settings.live_enabled:
        raise LiveDisabledError("Live mode is off (LIVE_ENABLED=false). Use Replay mode.")
    missing = [
        name
        for name, value in (
            ("TYPESAFE_API_KEY", settings.typesafe_api_key),
            ("OPENAI_API_KEY", settings.openai_api_key),
        )
        if value is None or not value.get_secret_value().strip()
    ]
    if missing or settings.typesafe_api_key is None or settings.openai_api_key is None:
        raise MissingKeyError(f"Live mode needs {', '.join(missing)} to be set.")
    return LiveClients(
        jev=LiveJevClient(api_key=settings.typesafe_api_key, model=settings.jev_model, guard=guard),
        llm=LiveOpenAIClient(
            api_key=settings.openai_api_key, model=settings.openai_model, guard=guard
        ),
    )
