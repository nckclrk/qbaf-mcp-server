from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from qbaf_mcp_server.backend import BackendClient, BackendError
from qbaf_mcp_server.models import (
    Claim,
    ExplainLocalRequest,
    NodeGetRequest,
    NodeSearchRequest,
    ProgressRequest,
    ScoreGetRequest,
    SubmitClaimsRequest,
)


@pytest.mark.asyncio
async def test_submit_claims_includes_graph_id() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "graph_id": "g_123",
                "results": [{"status": "created", "node_id": "n_1", "reason": "ok"}],
                "ingest_job_id": "job_1",
            },
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport, base_url="https://backend.local") as client:
        backend = BackendClient(client, "g_123")
        response = await backend.submit_claims(
            SubmitClaimsRequest(claims=[Claim(text="claim text")])
        )

    assert captured["url"] == "https://backend.local/ingest/claims"
    assert captured["method"] == "POST"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["graph_id"] == "g_123"
    assert response.graph_id == "g_123"
    assert response.ingest_job_id == "job_1"


@pytest.mark.asyncio
async def test_backend_error_translation() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"error": {"code": "NOT_FOUND", "message": "missing"}},
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport, base_url="https://backend.local") as client:
        backend = BackendClient(client, "g_123")
        with pytest.raises(BackendError) as exc:
            await backend.node_get(NodeGetRequest(node_id="n_missing"))

    assert exc.value.error.error.code == "NOT_FOUND"
    assert exc.value.error.error.message == "missing"


@pytest.mark.asyncio
async def test_backend_invalid_json_maps_to_internal_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="not-json")

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport, base_url="https://backend.local") as client:
        backend = BackendClient(client, "g_123")
        with pytest.raises(BackendError) as exc:
            await backend.node_search(NodeSearchRequest(query="q"))

    assert exc.value.error.error.code == "INTERNAL"
    assert "invalid JSON" in exc.value.error.error.message


@pytest.mark.asyncio
async def test_other_endpoints_delegate() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if "progress" in request.url.path:
            payload = {
                "graph_id": "g_123",
                "ingest_queue": {"pending": 0, "inflight": 0, "succeeded": 0, "failed": 0},
            }
        elif "scores" in request.url.path:
            payload = {"scores": []}
        else:
            payload = {"node_id": "n_1", "semantics": "sigmoid", "top": []}
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport, base_url="https://backend.local") as client:
        backend = BackendClient(client, "g_123")
        await backend.progress_get(ProgressRequest())
        await backend.score_get(ScoreGetRequest(node_ids=["n1", "n2"]))
        await backend.explain_local(ExplainLocalRequest(node_id="n1"))

    assert "progress" in seen[0]
    assert any("scores/batch" in url for url in seen)
    assert any("explain/local" in url for url in seen)
