from __future__ import annotations

import os

import pytest

from qbaf_mcp_server.config import Settings, SettingsError


def test_settings_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRAPH_ID", "g_123")
    monkeypatch.setenv("BACKEND_BASE_URL", "https://backend.local")
    monkeypatch.setenv("BACKEND_API_KEY", "abc123")
    monkeypatch.setenv("TIMEOUT_SECONDS", "5.5")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    settings = Settings.from_environment()

    assert settings.graph_id == "g_123"
    assert str(settings.backend_base_url) == "https://backend.local/"
    assert settings.backend_api_key == "abc123"
    assert settings.timeout_seconds == 5.5
    assert settings.log_level == "DEBUG"


def test_settings_missing_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GRAPH_ID", raising=False)
    monkeypatch.delenv("BACKEND_BASE_URL", raising=False)

    with pytest.raises(SettingsError) as exc:
        Settings.from_environment()

    assert "GRAPH_ID" in str(exc.value)
    assert "BACKEND_BASE_URL" in str(exc.value)


def test_settings_invalid_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRAPH_ID", "g_123")
    monkeypatch.setenv("BACKEND_BASE_URL", "https://backend.local")
    monkeypatch.setenv("TIMEOUT_SECONDS", "0")

    with pytest.raises(SettingsError):
        Settings.from_environment()


def test_settings_invalid_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GRAPH_ID", "g_123")
    monkeypatch.setenv("BACKEND_BASE_URL", "not-a-url")

    with pytest.raises(SettingsError):
        Settings.from_environment()


@pytest.fixture(autouse=True)
def clear_optional_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("GRAPH_ID", "BACKEND_BASE_URL", "BACKEND_API_KEY", "TIMEOUT_SECONDS", "LOG_LEVEL"):
        if key in os.environ:
            monkeypatch.delenv(key, raising=False)
