"""Shared objects live on app.state; routes get them through these dependencies."""

from collections.abc import Mapping

from fastapi import Request

from jev.api.errors import ApiError
from jev.config import Settings
from jev.runs.service import RunService
from jev.runs.store import RunStore


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_services(request: Request) -> Mapping[str, RunService]:
    """One run service per scenario id, in catalogue order."""
    services: Mapping[str, RunService] = request.app.state.services
    return services


def service_for(services: Mapping[str, RunService], scenario_id: str) -> RunService:
    """The scenario's run service, or a 404 envelope for an unknown id."""
    service = services.get(scenario_id)
    if service is None:
        raise ApiError(404, "UNKNOWN_SCENARIO", f"Unknown scenario {scenario_id!r}")
    return service


def get_runs(request: Request) -> RunStore:
    runs: RunStore = request.app.state.runs
    return runs
