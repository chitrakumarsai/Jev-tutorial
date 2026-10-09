"""Our own LLM request/result types. Pipelines depend on these, never on SDK types."""

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

DEFAULT_MAX_OUTPUT_TOKENS = 4_000

T = TypeVar("T", bound=BaseModel)


class LlmRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    instructions: str
    input: str
    purpose: str
    run_id: str = ""  # bookkeeping only; not sent and not part of the replay hash
    max_output_tokens: int = Field(default=DEFAULT_MAX_OUTPUT_TOKENS, gt=0)

    def payload(self, model: str, schema: type[BaseModel]) -> dict[str, JsonValue]:
        """Everything that determines the answer (used for replay hashing)."""
        return {
            "model": model,
            "instructions": self.instructions,
            "input": self.input,
            "max_output_tokens": self.max_output_tokens,
            "schema": schema.model_json_schema(),
        }


class LlmUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int
    output_tokens: int  # includes reasoning tokens
    reasoning_tokens: int = 0


class LlmResult(BaseModel, Generic[T]):
    """`parsed` is None when the model refused or returned output that doesn't fit the schema."""

    model_config = ConfigDict(frozen=True)

    model: str
    latency_ms: int
    usage: LlmUsage | None
    parsed: T | None
    refusal: str | None = None
    error: Literal["unparseable", "truncated", "content_filter"] | None = None
