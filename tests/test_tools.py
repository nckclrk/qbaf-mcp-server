from __future__ import annotations

import pytest
from mcp import server as mcp_server, types

from qbaf_mcp_server.backend import BackendError
from qbaf_mcp_server.models import (
    ErrorEnvelope,
    ErrorResponse,
    ExplainLocalItem,
    ExplainLocalRequest,
    ExplainLocalResponse,
    Node,
    NodeGetRequest,
    NodeGetResponse,
    NodeScore,
    NodeScoreValue,
    NodeSearchHit,
    NodeSearchRequest,
    NodeSearchResponse,
    ProgressRequest,
    ProgressResponse,
    QueueStats,
    ScoreGetRequest,
    ScoreGetResponse,
    SubmitClaimsRequest,
    SubmitClaimsResponse,
    SubmitClaimsResultItem,
)
from qbaf_mcp_server.tools import register


class StubBackend:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def submit_claims(self, payload: SubmitClaimsRequest) -> SubmitClaimsResponse:
        self.calls.append("submit")
        return SubmitClaimsResponse(
            graph_id="g_123",
            results=[SubmitClaimsResultItem(status="created", node_id="n_1", reason="ok")],
            ingest_job_id="job_1",
        )

    async def progress_get(self, payload: ProgressRequest) -> ProgressResponse:
        self.calls.append("progress")
        return ProgressResponse(
            graph_id="g_123",
            ingest_queue=QueueStats(pending=0, inflight=0, succeeded=1, failed=0),
        )

    async def node_search(self, payload: NodeSearchRequest) -> NodeSearchResponse:
        self.calls.append("search")
        return NodeSearchResponse(hits=[NodeSearchHit(node_id="n_1", text="claim", score=0.1)])

    async def node_get(self, payload: NodeGetRequest) -> NodeGetResponse:
        self.calls.append("get")
        return NodeGetResponse(
            node=Node(
                node_id="n_1",
                text="claim",
                score=NodeScore(value=0.5, semantics="sigmoid", at="now"),
            )
        )

    async def score_get(self, payload: ScoreGetRequest) -> ScoreGetResponse:
        self.calls.append("score")
        return ScoreGetResponse(scores=[NodeScoreValue(node_id="n_1", value=0.5)])

    async def explain_local(self, payload: ExplainLocalRequest) -> ExplainLocalResponse:
        self.calls.append("explain")
        return ExplainLocalResponse(
            node_id="n_1",
            semantics="sigmoid",
            top=[
                ExplainLocalItem(
                    from_id="n_2",
                    via_edge="e_1",
                    type="support",
                    marginal_contribution=0.1,
                )
            ],
        )


@pytest.mark.asyncio
async def test_list_tools_registers_all_tools() -> None:
    backend = StubBackend()
    app = mcp_server.Server(name="test")
    register(app, backend)

    handler = app.request_handlers[types.ListToolsRequest]
    result = await handler(types.ListToolsRequest())
    assert isinstance(result.root, types.ListToolsResult)
    tool_names = [tool.name for tool in result.root.tools]

    assert set(tool_names) == {
        "qbaf.claim.submit",
        "qbaf.progress.get",
        "qbaf.node.search",
        "qbaf.node.get",
        "qbaf.score.get",
        "qbaf.explain.local",
    }


@pytest.mark.asyncio
async def test_call_tool_success() -> None:
    backend = StubBackend()
    app = mcp_server.Server(name="test")
    register(app, backend)

    handler = app.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        params=types.CallToolRequestParams(
            name="qbaf.claim.submit",
            arguments={"claims": [{"text": "claim"}]},
        )
    )

    response = await handler(request)
    assert isinstance(response.root, types.CallToolResult)
    assert response.root.structuredContent is not None
    structured = response.root.structuredContent

    assert structured["graph_id"] == "g_123"
    assert backend.calls[0] == "submit"


@pytest.mark.asyncio
async def test_call_tool_validates_input() -> None:
    backend = StubBackend()
    app = mcp_server.Server(name="test")
    register(app, backend)

    handler = app.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        params=types.CallToolRequestParams(name="qbaf.claim.submit", arguments={}),
    )

    response = await handler(request)
    assert isinstance(response.root, types.CallToolResult)
    assert response.root.structuredContent is not None
    structured = response.root.structuredContent

    assert structured["error"]["code"] == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_call_tool_backend_error() -> None:
    class FailingBackend(StubBackend):
        async def node_get(self, payload: NodeGetRequest) -> NodeGetResponse:  # type: ignore[override]
            raise BackendError(
                ErrorResponse(error=ErrorEnvelope(code="NOT_FOUND", message="missing node"))
            )

    backend = FailingBackend()
    app = mcp_server.Server(name="test")
    register(app, backend)

    handler = app.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        params=types.CallToolRequestParams(name="qbaf.node.get", arguments={"node_id": "n_x"}),
    )

    response = await handler(request)
    assert isinstance(response.root, types.CallToolResult)
    assert response.root.structuredContent is not None
    structured = response.root.structuredContent

    assert structured["error"]["code"] == "NOT_FOUND"
    assert structured["error"]["message"] == "missing node"


@pytest.mark.asyncio
async def test_call_unknown_tool_raises_mcp_error() -> None:
    backend = StubBackend()
    app = mcp_server.Server(name="test")
    register(app, backend)

    handler = app.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        params=types.CallToolRequestParams(name="qbaf.unknown", arguments={}),
    )

    response = await handler(request)
    assert isinstance(response.root, types.CallToolResult)
    assert response.root.structuredContent is not None
    structured = response.root.structuredContent

    assert structured["error"]["code"] == "NOT_FOUND"
    assert "Unknown tool" in structured["error"]["message"]
