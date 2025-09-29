from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from qbaf_mcp_server.dev_backend import app, reset_state


@pytest.fixture(autouse=True)
def _reset_backend_state() -> None:
    reset_state()


@pytest.mark.asyncio
async def test_full_claim_flow() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://backend.local") as client:
        submit = await client.post(
            "/ingest/claims",
            json={
                "graph_id": "graph-1",
                "claims": [{"text": "Solar panels reduce emissions."}],
            },
        )

        assert submit.status_code == 200
        payload = submit.json()
        node_id = payload["results"][0]["node_id"]

        progress = await client.get("/progress", params={"graph_id": "graph-1"})
        assert progress.status_code == 200
        assert progress.json()["totals"]["nodes"] == 1

        search = await client.get(
            "/nodes/search",
            params={"graph_id": "graph-1", "q": "solar", "k": 5},
        )
        assert search.status_code == 200
        assert search.json()["hits"][0]["node_id"] == node_id

        node = await client.get(f"/nodes/{node_id}", params={"graph_id": "graph-1"})
        assert node.status_code == 200
        assert node.json()["node"]["text"].startswith("Solar panels")

        scores = await client.post(
            "/scores/batch",
            json={"graph_id": "graph-1", "node_ids": [node_id]},
        )
        assert scores.status_code == 200
        assert scores.json()["scores"][0]["node_id"] == node_id

        explain = await client.get(
            "/explain/local",
            params={"graph_id": "graph-1", "node_id": node_id, "k": 3},
        )
        assert explain.status_code == 200
        assert explain.json()["top"] == []


@pytest.mark.asyncio
async def test_missing_graph_id_errors() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://backend.local") as client:
        submit = await client.post("/ingest/claims", json={"claims": []})
        assert submit.status_code == 400
        body = submit.json()
        assert body["error"]["code"] == "INVALID_ARGUMENT"

        search = await client.get("/nodes/search")
        assert search.status_code == 400
