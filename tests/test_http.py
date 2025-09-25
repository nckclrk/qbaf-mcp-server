from __future__ import annotations

import httpx
import pytest

from qbaf_mcp_server.config import Settings
from qbaf_mcp_server.http import (
    BackendHealthError,
    backend_health_check,
    create_backend_client,
)


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("GRAPH_ID", "g_123")
    monkeypatch.setenv("BACKEND_BASE_URL", "https://backend.local")
    monkeypatch.setenv("BACKEND_API_KEY", "secret")
    monkeypatch.setenv("TIMEOUT_SECONDS", "3")

    return Settings.from_environment()


def test_create_backend_client_headers(settings: Settings) -> None:
    client = create_backend_client(settings)
    try:
        assert str(client.base_url) == "https://backend.local/"
        assert client.headers["Authorization"] == "Bearer secret"
        assert client.headers["User-Agent"].startswith("qbaf-mcp-server/")
    finally:
        asyncio_run(client.aclose())


def test_create_backend_client_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRAPH_ID", "g_123")
    monkeypatch.setenv("BACKEND_BASE_URL", "https://backend.local")

    settings = Settings.from_environment()

    client = create_backend_client(settings)
    try:
        assert "Authorization" not in client.headers
    finally:
        asyncio_run(client.aclose())


@pytest.mark.asyncio
async def test_backend_health_check_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/progress"
        assert request.url.params["graph_id"] == "g_123"
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport, base_url="https://backend.local") as client:
        await backend_health_check(client, "g_123")


@pytest.mark.asyncio
async def test_backend_health_check_error_on_server_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport, base_url="https://backend.local") as client:
        with pytest.raises(BackendHealthError):
            await backend_health_check(client, "g_123")


@pytest.mark.asyncio
async def test_backend_health_check_error_on_client_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport, base_url="https://backend.local") as client:
        with pytest.raises(BackendHealthError):
            await backend_health_check(client, "g_123")


def asyncio_run(awaitable) -> None:
    """Helper to run async cleanup in sync tests."""

    import asyncio

    asyncio.run(awaitable)
