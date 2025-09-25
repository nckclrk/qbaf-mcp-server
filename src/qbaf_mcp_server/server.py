"""Entry point utilities for the QBAF MCP server."""

from __future__ import annotations

import asyncio

import structlog

from .config import Settings, SettingsError
from .http import BackendHealthError, backend_health_check, create_backend_client
from .logging import configure_logging


async def startup() -> None:
    """Bootstrap logging, configuration, and backend connectivity."""

    settings = Settings.from_environment()
    configure_logging(settings.log_level)
    log = structlog.get_logger(__name__).bind(graph_id=settings.graph_id)

    log.info("startup_config_loaded")

    client = create_backend_client(settings)
    try:
        await backend_health_check(client, settings.graph_id)
    except BackendHealthError as exc:
        log.error("backend_health_failed", error=str(exc))
        raise
    else:
        log.info(
            "backend_health_ok",
            backend_base_url=str(settings.backend_base_url),
            timeout_seconds=settings.timeout_seconds,
        )
    finally:
        await client.aclose()


def main() -> None:
    """Synchronous entry point suitable for CLI execution."""

    try:
        asyncio.run(startup())
    except SettingsError as exc:
        raise SystemExit(f"configuration error: {exc}") from exc
    except BackendHealthError as exc:
        raise SystemExit(f"backend health check failed: {exc}") from exc


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()
