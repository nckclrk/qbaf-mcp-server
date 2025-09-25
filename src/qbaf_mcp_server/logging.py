"""Logging helpers for the QBAF MCP server."""

from __future__ import annotations

import logging

import structlog


def configure_logging(level: str) -> None:
    """Configure structlog with a JSON renderer."""

    logging.basicConfig(level=level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


__all__ = ["configure_logging"]
