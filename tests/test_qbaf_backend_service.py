from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient

from qbaf_backend.config import BackendSettings
import qbaf_backend.service as service_module
from qbaf_mcp_server.models import (
    ExplainLocalResponse,
    NodeGetResponse,
    Node,
    NodeScore,
    NodeSearchResponse,
    NodeSearchHit,
    ProgressResponse,
    QueueStats,
    RelationMiningStats,
    ScoreGetResponse,
    NodeScoreValue,
    SemanticsStats,
    SubmitClaimsResponse,
)


class StubRepository:
    def __init__(self, graph_id: str) -> None:
        self.graph_id = graph_id

    async def submit_claims(self, payload):  # noqa: ANN001 - test stub
        return SubmitClaimsResponse(graph_id=self.graph_id, results=[], ingest_job_id="job")

    async def progress_get(self, _payload):
        return ProgressResponse(
            graph_id=self.graph_id,
            ingest_queue=QueueStats(pending=0, inflight=0, succeeded=0, failed=0),
            relation_mining=RelationMiningStats(pending=0, edges_created=0),
            semantics=SemanticsStats(last_run_at=None, converged=True, iters=1),
            totals=None,
        )

    async def node_search(self, _payload):
        return NodeSearchResponse(hits=[NodeSearchHit(node_id="n1", text="test", score=1.0)])

    async def node_get(self, _payload):
        return NodeGetResponse(
            node=Node(node_id="n1", text="test", score=NodeScore(value=0.5, semantics="stored"))
        )

    async def score_get(self, _payload):
        return ScoreGetResponse(scores=[NodeScoreValue(node_id="n1", value=0.5)])

    async def explain_local(self, _payload):
        return ExplainLocalResponse(node_id="n1", semantics="stored", top=[])


class StubDriver:
    def close(self) -> None:  # pragma: no cover - trivial
        pass


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Any:
    settings = BackendSettings(
        graph_id="graph-1",
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
    )

    monkeypatch.setattr(service_module, "GraphDatabase", type("_Stub", (), {"driver": lambda *args, **kwargs: StubDriver()}))
    monkeypatch.setattr(service_module, "Neo4jRepository", lambda driver, graph_id: StubRepository(graph_id))

    return service_module.create_app(settings)


def test_submit_claims_endpoint(app: Any) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/ingest/claims",
            json={"graph_id": "graph-1", "claims": [{"text": "example"}]},
        )
        assert response.status_code == 200
        assert response.json()["graph_id"] == "graph-1"


def test_submit_claims_graph_mismatch(app: Any) -> None:
    with TestClient(app) as client:
        response = client.post(
            "/ingest/claims",
            json={"graph_id": "wrong", "claims": [{"text": "example"}]},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "INVALID_ARGUMENT"
