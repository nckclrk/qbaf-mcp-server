"""Top-level server bootstrap for the QBAF MCP service."""

from __future__ import annotations

import asyncio

import structlog
from dotenv import load_dotenv
from mcp import server as mcp_server
from mcp.server import stdio

from .backend import BackendClient, BackendError
from .config import Settings, SettingsError
from .http import BackendHealthError, backend_health_check, create_backend_client
from .logging import configure_logging
from .tools import register as register_tools

SERVER_NAME = "qbaf-mcp"
SERVER_VERSION = "0.1.0"


async def _run_server() -> None:
    load_dotenv()

    try:
        settings = Settings.from_environment()
    except SettingsError as exc:
        raise SystemExit(f"configuration error: {exc}") from exc

    configure_logging(settings.log_level)
    log = structlog.get_logger(__name__).bind(graph_id=settings.graph_id)

    http_client = create_backend_client(settings)
    backend = BackendClient(http_client, settings.graph_id)

    try:
        await backend_health_check(http_client, settings.graph_id)
    except BackendHealthError as exc:
        log.error("backend_health_failed", error=str(exc))
        await http_client.aclose()
        raise SystemExit(f"backend health check failed: {exc}") from exc

    app = mcp_server.Server(name=SERVER_NAME, version=SERVER_VERSION)
    register_tools(app, backend)
    initialization_options = app.create_initialization_options()
    log.info("server_startup_complete", backend_base_url=str(settings.backend_base_url))

    try:
        async with stdio.stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, initialization_options, raise_exceptions=False)
    finally:
        await http_client.aclose()
        log.info("server_shutdown")


def main() -> None:
    try:
        asyncio.run(_run_server())
    except SystemExit:
        raise
    except BackendError as exc:
        raise SystemExit(f"backend error: {exc}") from exc
    except Exception as exc:  # pragma: no cover - protective catch for stdio issues
        raise SystemExit(f"fatal error: {exc}") from exc


if __name__ == "__main__":  # pragma: no cover
    main()
