import pytest
from pydantic import ValidationError

from jev.api.schemas import ApiError, Envelope, Health


def test_ok_envelope_carries_data_and_no_error() -> None:
    envelope = Envelope.ok(Health(status="ok"))

    assert envelope.success is True
    assert envelope.data == Health(status="ok")
    assert envelope.error is None


def test_fail_envelope_carries_error_and_no_data() -> None:
    envelope: Envelope[Health] = Envelope.fail("BUDGET_EXCEEDED", "Cap reached")

    assert envelope.success is False
    assert envelope.data is None
    assert envelope.error == ApiError(code="BUDGET_EXCEEDED", message="Cap reached")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"success": True},
        {"success": False},
        {"success": True, "error": ApiError(code="X", message="y")},
        {"success": False, "data": Health(status="ok"), "error": ApiError(code="X", message="y")},
    ],
)
def test_contradictory_envelopes_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Envelope[Health](**kwargs)  # type: ignore[arg-type]
