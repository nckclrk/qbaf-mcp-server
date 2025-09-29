from __future__ import annotations

import pytest

from qbaf_backend.config import BackendSettings, BackendSettingsError


def test_backend_settings_from_env_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRAPH_ID", "graph-123")
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "password")

    settings = BackendSettings.from_environment()
    assert settings.graph_id == "graph-123"
    assert settings.neo4j_uri.startswith("bolt://")


def test_backend_settings_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("GRAPH_ID", "NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(BackendSettingsError):
        BackendSettings.from_environment()
