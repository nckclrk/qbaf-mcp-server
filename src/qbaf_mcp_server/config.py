"""Configuration utilities for the QBAF MCP server."""

from __future__ import annotations

import os
from typing import Any

from pydantic import AnyHttpUrl, Field, ValidationError
from pydantic import BaseModel as PydanticBaseModel
from pydantic import field_validator


class Settings(PydanticBaseModel):
    """Validated settings loaded from environment variables."""

    graph_id: str = Field(alias="GRAPH_ID")
    backend_base_url: AnyHttpUrl = Field(alias="BACKEND_BASE_URL")
    backend_api_key: str | None = Field(default=None, alias="BACKEND_API_KEY")
    timeout_seconds: float = Field(default=10.0, alias="TIMEOUT_SECONDS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = {
        "populate_by_name": True,
        "str_strip_whitespace": True,
        "extra": "forbid",
    }

    @field_validator("graph_id")
    @classmethod
    def _graph_id_not_blank(cls, value: str) -> str:
        if not value:
            raise ValueError("GRAPH_ID must be non-empty")
        return value

    @field_validator("timeout_seconds")
    @classmethod
    def _timeout_positive(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("TIMEOUT_SECONDS must be positive")
        return value

    @field_validator("log_level")
    @classmethod
    def _log_level_upper(cls, value: str) -> str:
        return value.upper()

    @classmethod
    def from_environment(cls) -> "Settings":
        """Create a settings instance from OS environment variables."""

        raw: dict[str, Any] = {}
        for key in (
            "GRAPH_ID",
            "BACKEND_BASE_URL",
            "BACKEND_API_KEY",
            "TIMEOUT_SECONDS",
            "LOG_LEVEL",
        ):
            value = os.environ.get(key)
            if value is not None:
                raw[key] = value

        try:
            return cls(**raw)
        except ValidationError as exc:  # pragma: no cover - rewrap for clarity
            message = "; ".join((
                ".".join(str(loc_part) for loc_part in error["loc"])
                + f": {error['msg']}"
                for error in exc.errors()
            ))
            raise SettingsError(message) from exc


class SettingsError(RuntimeError):
    """Raised when configuration could not be loaded."""


__all__ = ["Settings", "SettingsError"]
