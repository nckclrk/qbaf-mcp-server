"""Starlette application exposing the Neo4j-backed QBAF API."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

import structlog
from neo4j import GraphDatabase
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from qbaf_mcp_server.models import (
    ErrorEnvelope,
    ErrorResponse,
    ExplainLocalRequest,
    NodeGetRequest,
    NodeSearchRequest,
    ProgressRequest,
    ScoreGetRequest,
    SubmitClaimsRequest,
)

from .config import BackendSettings, BackendSettingsError
from .repository import Neo4jRepository


log = structlog.get_logger(__name__)


def _error_response(code: str, message: str, status: int, details: dict[str, Any] | None = None) -> JSONResponse:
    payload = ErrorResponse(error=ErrorEnvelope(code=code, message=message, details=details))
    return JSONResponse(payload.model_dump(mode="json"), status_code=status)


def create_app(settings: BackendSettings | None = None) -> Starlette:
    if settings is None:
        load_dotenv()
        try:
            settings = BackendSettings.from_environment()
        except BackendSettingsError as exc:  # pragma: no cover - defensive
            raise RuntimeError(f"backend configuration error: {exc}") from exc

    driver = GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password))
    repository = Neo4jRepository(driver, settings.graph_id)

    async def submit_claims(request: Request) -> JSONResponse:
        body = await request.json()
        if body.get("graph_id") != settings.graph_id:
            return _error_response("INVALID_ARGUMENT", "graph_id mismatch", 400)
        try:
            payload = SubmitClaimsRequest.model_validate(body)
        except Exception as exc:  # noqa: BLE001
            return _error_response("INVALID_ARGUMENT", "invalid payload", 400, {"hint": str(exc)})
        response = await repository.submit_claims(payload)
        return JSONResponse(response.model_dump(mode="json"))

    async def progress_get(request: Request) -> JSONResponse:
        graph_id = request.query_params.get("graph_id")
        if graph_id != settings.graph_id:
            return _error_response("INVALID_ARGUMENT", "graph_id mismatch", 400)
        payload = ProgressRequest(ingest_job_id=request.query_params.get("job_id"))
        response = await repository.progress_get(payload)
        return JSONResponse(response.model_dump(mode="json"))

    async def node_search(request: Request) -> JSONResponse:
        graph_id = request.query_params.get("graph_id")
        if graph_id != settings.graph_id:
            return _error_response("INVALID_ARGUMENT", "graph_id mismatch", 400)
        payload_dict: Dict[str, Any] = {"query": request.query_params.get("q", "")}
        top_k = request.query_params.get("k")
        if top_k is not None:
            payload_dict["top_k"] = top_k
        tags = request.query_params.get("tags")
        if tags:
            payload_dict["filter"] = {"tags_any": [tag.strip() for tag in tags.split(",") if tag.strip()]}
        try:
            payload = NodeSearchRequest.model_validate(payload_dict)
        except Exception as exc:  # noqa: BLE001
            return _error_response("INVALID_ARGUMENT", "invalid query", 400, {"hint": str(exc)})
        response = await repository.node_search(payload)
        return JSONResponse(response.model_dump(mode="json"))

    async def node_get(request: Request) -> JSONResponse:
        graph_id = request.query_params.get("graph_id")
        if graph_id != settings.graph_id:
            return _error_response("INVALID_ARGUMENT", "graph_id mismatch", 400)
        payload = NodeGetRequest(node_id=request.path_params["node_id"])
        response = await repository.node_get(payload)
        if response is None:
            return _error_response("NOT_FOUND", "node not found", 404)
        return JSONResponse(response.model_dump(mode="json"))

    async def score_get(request: Request) -> JSONResponse:
        body = await request.json()
        if body.get("graph_id") != settings.graph_id:
            return _error_response("INVALID_ARGUMENT", "graph_id mismatch", 400)
        try:
            payload = ScoreGetRequest.model_validate({"node_ids": body.get("node_ids")})
        except Exception as exc:  # noqa: BLE001
            return _error_response("INVALID_ARGUMENT", "invalid payload", 400, {"hint": str(exc)})
        response = await repository.score_get(payload)
        return JSONResponse(response.model_dump(mode="json"))

    async def explain_local(request: Request) -> JSONResponse:
        graph_id = request.query_params.get("graph_id")
        if graph_id != settings.graph_id:
            return _error_response("INVALID_ARGUMENT", "graph_id mismatch", 400)
        payload_dict: Dict[str, Any] = {"node_id": request.query_params.get("node_id")}
        k_value = request.query_params.get("k")
        if k_value is not None:
            payload_dict["k"] = k_value
        mode = request.query_params.get("mode")
        if mode is not None:
            payload_dict["mode"] = mode
        try:
            payload = ExplainLocalRequest.model_validate(payload_dict)
        except Exception as exc:  # noqa: BLE001
            return _error_response("INVALID_ARGUMENT", "invalid query", 400, {"hint": str(exc)})
        response = await repository.explain_local(payload)
        if response is None:
            return _error_response("NOT_FOUND", "node not found", 404)
        return JSONResponse(response.model_dump(mode="json"))

    routes = [
        Route("/ingest/claims", submit_claims, methods=["POST"]),
        Route("/progress", progress_get, methods=["GET"]),
        Route("/nodes/search", node_search, methods=["GET"]),
        Route("/nodes/{node_id}", node_get, methods=["GET"]),
        Route("/scores/batch", score_get, methods=["POST"]),
        Route("/explain/local", explain_local, methods=["GET"]),
    ]

    app = Starlette(debug=True, routes=routes)

    @app.on_event("shutdown")
    async def _shutdown() -> None:  # pragma: no cover - simple resource cleanup
        await asyncio.to_thread(driver.close)

    return app


__all__ = ["create_app"]
