"""HTTP utilities for interacting with the QBAF backend."""

from __future__ import annotations

import httpx

from .config import Settings

USER_AGENT = "qbaf-mcp-server/0.1.0"


class BackendHealthError(RuntimeError):
    """Raised when the backend health check fails."""


def create_backend_client(settings: Settings) -> httpx.AsyncClient:
    """Create an AsyncClient configured for the QBAF backend."""

    headers: dict[str, str] = {"User-Agent": USER_AGENT}
    if settings.backend_api_key:
        headers["Authorization"] = f"Bearer {settings.backend_api_key}"

    timeout = httpx.Timeout(settings.timeout_seconds)

    return httpx.AsyncClient(
        base_url=str(settings.backend_base_url),
        timeout=timeout,
        headers=headers,
        limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )


async def backend_health_check(client: httpx.AsyncClient, graph_id: str) -> None:
    """Perform a lightweight read to verify backend connectivity."""

    try:
        response = await client.get("/progress", params={"graph_id": graph_id}, timeout=client.timeout)
    except httpx.HTTPError as exc:  # pragma: no cover - passthrough for clarity
        raise BackendHealthError("backend unreachable") from exc

    if response.status_code == 404:
        return

    if response.status_code >= 500:
        raise BackendHealthError(
            f"backend unhealthy: status_code={response.status_code}",
        )

    if response.status_code >= 400:
        raise BackendHealthError(
            f"backend rejected health probe: status_code={response.status_code}",
        )


__all__ = [
    "BackendHealthError",
    "backend_health_check",
    "create_backend_client",
]
