"""FastAPI application factory. Local-only: trusted hosts and the Vite dev origin."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from jev import __version__
from jev.api.errors import install_error_handlers
from jev.api.routes import budget, runs, scenarios
from jev.api.schemas import Envelope, Health
from jev.config import Settings
from jev.runs.service import RunService
from jev.runs.store import RunStore


def create_app(settings: Settings | None = None, service: RunService | None = None) -> FastAPI:
    """Build the API app. Pass `settings`/`service` to inject test doubles."""
    settings = settings or Settings()
    app = FastAPI(title="Jev Audit Lens", version=__version__)
    app.state.settings = settings
    app.state.service = service or RunService(settings)
    app.state.runs = RunStore()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["content-type"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    install_error_handlers(app)

    @app.get("/api/health", response_model=Envelope[Health])
    def health() -> Envelope[Health]:
        return Envelope.ok(Health(status="ok"))

    for module in (scenarios, runs, budget):
        app.include_router(module.router)
    return app
