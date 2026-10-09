"""FastAPI application factory."""

from fastapi import FastAPI

from jev import __version__
from jev.api.schemas import Envelope, Health


def create_app() -> FastAPI:
    """Build the API app. Routers are registered here as features land."""
    app = FastAPI(title="Jev Audit Lens", version=__version__)

    @app.get("/api/health", response_model=Envelope[Health])
    def health() -> Envelope[Health]:
        return Envelope.ok(Health(status="ok"))

    return app
