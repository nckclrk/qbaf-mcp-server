"""Configuration utilities for the Neo4j-backed QBAF service."""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator


class BackendSettings(BaseModel):
    """Environment-driven settings for the Neo4j service."""

    graph_id: str = Field(alias="GRAPH_ID")
    neo4j_uri: str = Field(alias="NEO4J_URI")
    neo4j_user: str = Field(alias="NEO4J_USERNAME")
    neo4j_password: str = Field(alias="NEO4J_PASSWORD")

    model_config = {
        "populate_by_name": True,
        "str_strip_whitespace": True,
        "extra": "forbid",
    }

    @field_validator("graph_id", "neo4j_uri", "neo4j_user", "neo4j_password")
    @classmethod
    def _not_blank(cls, value: str, field: Any) -> str:
        if not value:
            raise ValueError(f"{field.alias} must be non-empty")
        return value

    @classmethod
    def from_environment(cls) -> "BackendSettings":
        raw: dict[str, Any] = {}
        for key in ("GRAPH_ID", "NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"):
            value = os.environ.get(key)
            if value is not None:
                raw[key] = value
        try:
            return cls(**raw)
        except ValidationError as exc:  # pragma: no cover - rewrap
            message = "; ".join(
                ".".join(str(part) for part in error["loc"]) + f": {error['msg']}"
                for error in exc.errors()
            )
            raise BackendSettingsError(message) from exc


class BackendSettingsError(RuntimeError):
    """Raised when configuration fails."""


__all__ = ["BackendSettings", "BackendSettingsError"]
