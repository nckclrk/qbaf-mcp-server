"""Minimal local backend implementation for manual testing."""

from __future__ import annotations

import asyncio
import math
from typing import Dict, Iterable, List

import ulid
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .models import (
    Claim,
    ExplainLocalItem,
    ExplainLocalRequest,
    ExplainLocalResponse,
    Node,
    NodeGetResponse,
    NodeScore,
    NodeScoreValue,
    NodeSearchHit,
    NodeSearchRequest,
    NodeSearchResponse,
    ProgressRequest,
    ProgressResponse,
    QueueStats,
    RelationMiningStats,
    ScoreGetRequest,
    ScoreGetResponse,
    SemanticsStats,
    SubmitClaimsRequest,
    SubmitClaimsResponse,
    SubmitClaimsResultItem,
    Totals,
)


def _json_error(status: int, code: str, message: str) -> JSONResponse:
    payload = {"error": {"code": code, "message": message}}
    return JSONResponse(payload, status_code=status)


class GraphData:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.nodes: Dict[str, Node] = {}
        self.scores: Dict[str, float] = {}
        self.ingest_jobs: Dict[str, int] = {}

    async def submit_claims(self, graph_id: str, payload: SubmitClaimsRequest) -> SubmitClaimsResponse:
        async with self._lock:
            job_id = str(ulid.new())
            results: List[SubmitClaimsResultItem] = []
            for claim in payload.claims:
                node_id = str(ulid.new())
                node = Node(
                    node_id=node_id,
                    text=claim.text,
                    canonical=claim.canonical,
                    provenance=[claim.source] if claim.source else None,
                    meta=claim.meta,
                    score=NodeScore(value=self._initial_score(claim), semantics="baseline"),
                )
                self.nodes[node_id] = node
                self.scores[node_id] = node.score.value
                results.append(SubmitClaimsResultItem(status="created", node_id=node_id))
            self.ingest_jobs[job_id] = len(results)
            return SubmitClaimsResponse(graph_id=graph_id, results=results, ingest_job_id=job_id or None)

    async def progress(self, graph_id: str, payload: ProgressRequest) -> ProgressResponse:
        async with self._lock:
            total_nodes = len(self.nodes)
            queue = QueueStats(pending=0, inflight=0, succeeded=total_nodes, failed=0)
            relation = RelationMiningStats(pending=0, edges_created=0)
            semantics = SemanticsStats(last_run_at=None, converged=True, iters=1)
            totals = Totals(nodes=total_nodes, edges=0)
            return ProgressResponse(
                graph_id=graph_id,
                ingest_queue=queue,
                relation_mining=relation,
                semantics=semantics,
                totals=totals,
            )

    async def node_search(self, payload: NodeSearchRequest) -> NodeSearchResponse:
        async with self._lock:
            query = payload.query.lower()
            matches: Iterable[Node] = (
                node for node in self.nodes.values() if query in node.text.lower()
            )
            hits: List[NodeSearchHit] = []
            for node in matches:
                score = self.scores.get(node.node_id)
                hits.append(NodeSearchHit(node_id=node.node_id, text=node.text, score=score))
                if len(hits) >= payload.top_k:
                    break
            return NodeSearchResponse(hits=hits)

    async def node_get(self, node_id: str) -> NodeGetResponse | None:
        async with self._lock:
            node = self.nodes.get(node_id)
            if node is None:
                return None
            return NodeGetResponse(node=node)

    async def scores_for(self, node_ids: Iterable[str]) -> ScoreGetResponse:
        async with self._lock:
            values = [
                NodeScoreValue(node_id=node_id, value=self.scores.get(node_id, math.nan))
                for node_id in node_ids
            ]
            return ScoreGetResponse(scores=values)

    async def explain_local(self, payload: ExplainLocalRequest) -> ExplainLocalResponse | None:
        async with self._lock:
            if payload.node_id not in self.nodes:
                return None
            top: List[ExplainLocalItem] = []
            return ExplainLocalResponse(node_id=payload.node_id, semantics="baseline", top=top)

    @staticmethod
    def _initial_score(claim: Claim) -> float:
        base = 0.5
        length_bonus = min(len(claim.text) / 200, 0.4)
        return round(base + length_bonus, 3)


class GraphRegistry:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._graphs: Dict[str, GraphData] = {}

    async def get(self, graph_id: str) -> GraphData | None:
        async with self._lock:
            return self._graphs.get(graph_id)

    async def get_or_create(self, graph_id: str) -> GraphData:
        async with self._lock:
            graph = self._graphs.get(graph_id)
            if graph is None:
                graph = GraphData()
                self._graphs[graph_id] = graph
            return graph


registry = GraphRegistry()


def reset_state() -> None:
    """Reset backend state (primarily for tests)."""

    global registry
    registry = GraphRegistry()


async def ingest_claims(request: Request) -> JSONResponse:
    data = await request.json()
    graph_id = data.get("graph_id")
    if not isinstance(graph_id, str):
        return _json_error(400, "INVALID_ARGUMENT", "graph_id is required")

    body = {key: data.get(key) for key in ("claims", "dedupe", "client_token") if key in data}
    try:
        payload = SubmitClaimsRequest.model_validate(body)
    except Exception as exc:  # noqa: BLE001 - convert to json error
        return _json_error(400, "INVALID_ARGUMENT", str(exc))

    graph = await registry.get_or_create(graph_id)
    response = await graph.submit_claims(graph_id, payload)
    return JSONResponse(response.model_dump(mode="json"))


async def progress_get(request: Request) -> JSONResponse:
    graph_id = request.query_params.get("graph_id")
    if not graph_id:
        return _json_error(400, "INVALID_ARGUMENT", "graph_id query parameter is required")

    graph = await registry.get(graph_id)
    if graph is None:
        return _json_error(404, "NOT_FOUND", "graph not found")

    payload = ProgressRequest(ingest_job_id=request.query_params.get("job_id"))
    response = await graph.progress(graph_id, payload)
    return JSONResponse(response.model_dump(mode="json"))


async def node_search(request: Request) -> JSONResponse:
    graph_id = request.query_params.get("graph_id")
    if not graph_id:
        return _json_error(400, "INVALID_ARGUMENT", "graph_id query parameter is required")

    graph = await registry.get(graph_id)
    if graph is None:
        return _json_error(404, "NOT_FOUND", "graph not found")

    payload_dict = {"query": request.query_params.get("q", "")}
    top_k = request.query_params.get("k")
    if top_k is not None:
        payload_dict["top_k"] = top_k
    tags = request.query_params.get("tags")
    if tags:
        payload_dict["filter"] = {"tags_any": [tag.strip() for tag in tags.split(",") if tag.strip()]}

    try:
        payload = NodeSearchRequest.model_validate(payload_dict)
    except Exception as exc:  # noqa: BLE001
        return _json_error(400, "INVALID_ARGUMENT", str(exc))

    response = await graph.node_search(payload)
    return JSONResponse(response.model_dump(mode="json"))


async def node_get(request: Request) -> JSONResponse:
    graph_id = request.query_params.get("graph_id")
    if not graph_id:
        return _json_error(400, "INVALID_ARGUMENT", "graph_id query parameter is required")

    graph = await registry.get(graph_id)
    if graph is None:
        return _json_error(404, "NOT_FOUND", "graph not found")

    node_id = request.path_params.get("node_id")
    response = await graph.node_get(node_id)
    if response is None:
        return _json_error(404, "NOT_FOUND", "node not found")
    return JSONResponse(response.model_dump(mode="json"))


async def score_get(request: Request) -> JSONResponse:
    data = await request.json()
    graph_id = data.get("graph_id")
    if not isinstance(graph_id, str):
        return _json_error(400, "INVALID_ARGUMENT", "graph_id is required")

    graph = await registry.get(graph_id)
    if graph is None:
        return _json_error(404, "NOT_FOUND", "graph not found")

    try:
        payload = ScoreGetRequest.model_validate({"node_ids": data.get("node_ids")})
    except Exception as exc:  # noqa: BLE001
        return _json_error(400, "INVALID_ARGUMENT", str(exc))

    response = await graph.scores_for(payload.node_ids)
    return JSONResponse(response.model_dump(mode="json"))


async def explain_local(request: Request) -> JSONResponse:
    graph_id = request.query_params.get("graph_id")
    if not graph_id:
        return _json_error(400, "INVALID_ARGUMENT", "graph_id query parameter is required")

    graph = await registry.get(graph_id)
    if graph is None:
        return _json_error(404, "NOT_FOUND", "graph not found")

    payload_dict = {"node_id": request.query_params.get("node_id")}
    k_value = request.query_params.get("k")
    if k_value is not None:
        payload_dict["k"] = k_value
    mode = request.query_params.get("mode")
    if mode is not None:
        payload_dict["mode"] = mode
    try:
        payload = ExplainLocalRequest.model_validate(payload_dict)
    except Exception as exc:  # noqa: BLE001
        return _json_error(400, "INVALID_ARGUMENT", str(exc))

    response = await graph.explain_local(payload)
    if response is None:
        return _json_error(404, "NOT_FOUND", "node not found")
    return JSONResponse(response.model_dump(mode="json"))


routes = [
    Route("/ingest/claims", ingest_claims, methods=["POST"]),
    Route("/progress", progress_get, methods=["GET"]),
    Route("/nodes/search", node_search, methods=["GET"]),
    Route("/nodes/{node_id}", node_get, methods=["GET"]),
    Route("/scores/batch", score_get, methods=["POST"]),
    Route("/explain/local", explain_local, methods=["GET"]),
]

app = Starlette(debug=True, routes=routes)


__all__ = ["app", "reset_state"]
