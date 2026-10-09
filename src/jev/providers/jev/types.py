"""Our own Jev request/answer types. Pipelines depend on these, never on SDK types."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

MAX_CHOICE_OPTIONS = 255
MIN_SCORE_LEVELS, MAX_SCORE_LEVELS = 2, 10

Instructions = str | dict[str, JsonValue] | list[JsonValue]
# Option / level descriptions: text, or structured JSON (TypeSafe "Advanced: structure").
Description = str | dict[str, JsonValue] | list[JsonValue]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ChoiceQ(_Frozen):
    """Pick one option. Criteria map option -> description (or None)."""

    type: Literal["choice"] = "choice"
    instructions: Instructions
    criteria: dict[str, Description | None] = Field(min_length=1, max_length=MAX_CHOICE_OPTIONS)


class ScoreQ(_Frozen):
    """Rate on an ordered rubric of 2–10 levels."""

    type: Literal["score"] = "score"
    instructions: Instructions
    criteria: tuple[Description, ...] = Field(
        min_length=MIN_SCORE_LEVELS, max_length=MAX_SCORE_LEVELS
    )


class NoulCriteriaQ(_Frozen):
    true: Description | None = None
    false: Description | None = None


class NoulQ(_Frozen):
    """Probability that a statement is true."""

    type: Literal["noul"] = "noul"
    instructions: Instructions
    criteria: NoulCriteriaQ | None = None


Question = Annotated[ChoiceQ | ScoreQ | NoulQ, Field(discriminator="type")]


class JevRequest(_Frozen):
    """One state evaluated against several independent questions in a single call."""

    state: JsonValue
    questions: dict[str, Question] = Field(min_length=1)
    purpose: str  # e.g. "s1.contract_terms": a label for events and replay files
    run_id: str = ""  # bookkeeping only; not sent and not part of the replay hash

    def payload(self, model: str) -> dict[str, JsonValue]:
        """The exact API body, with questions in a stable order (used for replay hashing)."""
        return {
            "model": model,
            "state": self.state,
            "questions": {
                key: self.questions[key].model_dump(mode="json", exclude_none=True)
                for key in sorted(self.questions)
            },
        }


class Usage(_Frozen):
    input_tokens: int | None
    output_tokens: int | None


class ChoiceA(_Frozen):
    choice: str
    probabilities: dict[str, float]
    confidence: float


class ScoreA(_Frozen):
    score: float
    probabilities: dict[str, float]
    confidence: float


class NoulA(_Frozen):
    noul: float

    @property
    def confidence(self) -> float:
        """Distance from a coin flip, as defined in TypeSafe's confidence docs: |2p - 1|."""
        return abs(2 * self.noul - 1)


class JevResult(_Frozen):
    model: str
    latency_ms: int
    choices: dict[str, ChoiceA]
    scores: dict[str, ScoreA]
    nouls: dict[str, NoulA]
    usage: Usage
