"""Response envelope shared by every JSON endpoint."""

from typing import Generic, Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict, model_validator

T = TypeVar("T")


class ApiError(BaseModel):
    """Machine-readable error code plus a user-presentable message."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str


class Envelope(BaseModel, Generic[T]):
    """`{success, data, error}`: data is set on success, error on failure, never both."""

    model_config = ConfigDict(frozen=True)

    success: bool
    data: T | None = None
    error: ApiError | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.success and (self.data is None or self.error is not None):
            raise ValueError("a successful envelope needs data and no error")
        if not self.success and (self.error is None or self.data is not None):
            raise ValueError("a failed envelope needs an error and no data")
        return self

    @classmethod
    def ok(cls, data: T) -> "Envelope[T]":
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, code: str, message: str) -> "Envelope[T]":
        return cls(success=False, error=ApiError(code=code, message=message))


class Health(BaseModel):
    """Liveness payload for `GET /api/health`."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
