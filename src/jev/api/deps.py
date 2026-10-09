"""Shared objects live on app.state; routes get them through these dependencies."""

from fastapi import Request

from jev.config import Settings
from jev.runs.service import RunService
from jev.runs.store import RunStore


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_service(request: Request) -> RunService:
    service: RunService = request.app.state.service
    return service


def get_runs(request: Request) -> RunStore:
    runs: RunStore = request.app.state.runs
    return runs
