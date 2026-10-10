"""FastAPI application factory. Local-only: trusted hosts and the Vite dev origin."""

from collections.abc import Mapping

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
from jev.scenarios.registry import SCENARIOS


def _default_services(settings: Settings) -> dict[str, RunService]:
    return {spec.id: RunService(settings, scenario=spec) for spec in SCENARIOS}


def _services(
    settings: Settings, service: RunService | None, services: Mapping[str, RunService] | None
) -> dict[str, RunService]:
    """Every scenario's service is built at startup, so bad scenario data fails fast."""
    if service is not None and services is not None:
        raise ValueError("Pass either `service` or `services`, not both.")
    if services is None:
        services = {service.scenario.id: service} if service else _default_services(settings)
    for key, svc in services.items():
        if key != svc.scenario.id:
            raise ValueError(f"Service registered as {key!r} runs {svc.scenario.id!r}.")
    return dict(services)


def create_app(
    settings: Settings | None = None,
    service: RunService | None = None,
    services: Mapping[str, RunService] | None = None,
) -> FastAPI:
    """Build the API app. Pass `settings` and one `service` (or `services`, one per scenario
    id, in catalogue order) to inject test doubles."""
    settings = settings or Settings()
    app = FastAPI(title="Jev Audit Lens", version=__version__)
    app.state.settings = settings
    app.state.services = _services(settings, service, services)
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
