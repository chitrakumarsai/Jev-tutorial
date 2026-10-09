"""Runtime settings, read from the environment (and the git-ignored dotenv file) and validated."""

from decimal import Decimal
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Presenter constraint (docs/adr/0002): lifetime spend per API key never exceeds this.
HARD_BUDGET_CAP_USD = Decimal("5.00")
DEFAULT_REVIEW_THRESHOLD = 0.8


class Settings(BaseSettings):
    """All runtime configuration. Live mode is off unless explicitly enabled."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True
    )

    typesafe_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-6-luna"
    jev_model: str = "jev-latest"
    live_enabled: bool = False
    # May be lowered via env, never raised above the hard cap.
    budget_cap_usd: Decimal = Field(default=HARD_BUDGET_CAP_USD, gt=0, le=HARD_BUDGET_CAP_USD)
    review_threshold: float = Field(default=DEFAULT_REVIEW_THRESHOLD, gt=0, lt=1)
    # The API is local-only: trusted Host headers (DNS-rebinding defence) and the Vite origin.
    allowed_hosts: list[str] = ["127.0.0.1", "localhost"]
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Anchored to the project root, not the working directory, so running from another
    # folder can't silently start a fresh budget (ADR 0002).
    ledger_path: Path = PROJECT_ROOT / "var" / "ledger.jsonl"

    @field_validator("ledger_path")
    @classmethod
    def _anchor_to_project_root(cls, path: Path) -> Path:
        return path if path.is_absolute() else PROJECT_ROOT / path
