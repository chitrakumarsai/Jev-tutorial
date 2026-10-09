"""Latency, token and cost metrics for one side of a run."""

from collections.abc import Sequence
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from jev.budget.pricing import cost_usd


class CallUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    input_tokens: int | None
    output_tokens: int | None


class Metrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    latency_ms: int  # wall-clock for the side, not the sum of concurrent calls
    requests: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal | None  # None when any call's usage is unknown: unknown, not wrong


def metrics_for(model: str, usages: Sequence[CallUsage], *, wall_ms: int) -> Metrics:
    known = all(u.input_tokens is not None and u.output_tokens is not None for u in usages)
    inputs = sum(u.input_tokens or 0 for u in usages)
    outputs = sum(u.output_tokens or 0 for u in usages)
    return Metrics(
        latency_ms=wall_ms,
        requests=len(usages),
        input_tokens=inputs,
        output_tokens=outputs,
        cost_usd=cost_usd(model, inputs, outputs) if known else None,
    )
