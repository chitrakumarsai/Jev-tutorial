"""Every failure becomes the same `{success: false, error: {code, message}}` envelope."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from jev.api.schemas import Envelope
from jev.budget.guard import BudgetExceededError
from jev.budget.ledger import LedgerCorruptError, LedgerMissingError
from jev.budget.pricing import UnknownModelError
from jev.providers.factory import LiveDisabledError, MissingKeyError
from jev.replay.store import ReplayStoreError
from jev.runs.service import NoRecordingError


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


# Domain error -> (HTTP status, code). Messages are our own; they never contain keys.
DOMAIN_ERRORS: dict[type[Exception], tuple[int, str]] = {
    LiveDisabledError: (403, "LIVE_DISABLED"),
    BudgetExceededError: (409, "BUDGET_EXCEEDED"),
    MissingKeyError: (409, "MISSING_KEYS"),
    LedgerMissingError: (409, "LEDGER_MISSING"),
    LedgerCorruptError: (409, "LEDGER_CORRUPT"),
    UnknownModelError: (409, "UNKNOWN_MODEL"),
    NoRecordingError: (404, "NO_RECORDING"),
    ReplayStoreError: (404, "NO_RECORDING"),
}


def _envelope(status: int, code: str, message: str) -> JSONResponse:
    body = Envelope[None].fail(code, message).model_dump(mode="json")
    return JSONResponse(status_code=status, content=body)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _envelope(exc.status, exc.code, exc.message)

    for error_type, (status, code) in DOMAIN_ERRORS.items():

        async def domain_error(
            _: Request, exc: Exception, status: int = status, code: str = code
        ) -> JSONResponse:
            return _envelope(status, code, str(exc))

        app.add_exception_handler(error_type, domain_error)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", ()))
        return _envelope(422, "INVALID_REQUEST", f"{where}: {first.get('msg', 'invalid request')}")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _envelope(exc.status_code, "HTTP_ERROR", str(exc.detail))
