"""MCP tool registration for the QBAF server."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Generic, Mapping, TypeVar

import structlog
from mcp import server, types
from pydantic import BaseModel, ValidationError

from .backend import BackendError, BackendProtocol
from .models import (
    ErrorEnvelope,
    ErrorResponse,
    ExplainLocalRequest,
    ExplainLocalResponse,
    NodeGetRequest,
    NodeGetResponse,
    NodeSearchRequest,
    NodeSearchResponse,
    ProgressRequest,
    ProgressResponse,
    ScoreGetRequest,
    ScoreGetResponse,
    SubmitClaimsRequest,
    SubmitClaimsResponse,
)

logger = structlog.get_logger(__name__)


ReqT = TypeVar("ReqT", bound=BaseModel)
ResT = TypeVar("ResT", bound=BaseModel)


@dataclass
class ToolDefinition(Generic[ReqT, ResT]):
    name: str
    description: str
    request_model: type[ReqT]
    response_model: type[ResT]
    handler: Callable[[BackendProtocol, ReqT], Awaitable[ResT]]


async def _handle_claim_submit(backend: BackendProtocol, payload: SubmitClaimsRequest) -> SubmitClaimsResponse:
    return await backend.submit_claims(payload)


async def _handle_progress_get(backend: BackendProtocol, payload: ProgressRequest) -> ProgressResponse:
    return await backend.progress_get(payload)


async def _handle_node_search(backend: BackendProtocol, payload: NodeSearchRequest) -> NodeSearchResponse:
    return await backend.node_search(payload)


async def _handle_node_get(backend: BackendProtocol, payload: NodeGetRequest) -> NodeGetResponse:
    return await backend.node_get(payload)


async def _handle_score_get(backend: BackendProtocol, payload: ScoreGetRequest) -> ScoreGetResponse:
    return await backend.score_get(payload)


async def _handle_explain_local(backend: BackendProtocol, payload: ExplainLocalRequest) -> ExplainLocalResponse:
    return await backend.explain_local(payload)


TOOL_DEFINITIONS: Mapping[str, ToolDefinition[Any, Any]] = {
    "qbaf.claim.submit": ToolDefinition(
        name="qbaf.claim.submit",
        description="Submit claims to the fixed graph.",
        request_model=SubmitClaimsRequest,
        response_model=SubmitClaimsResponse,
        handler=_handle_claim_submit,
    ),
    "qbaf.progress.get": ToolDefinition(
        name="qbaf.progress.get",
        description="Get ingestion, mining, and semantics progress for the graph.",
        request_model=ProgressRequest,
        response_model=ProgressResponse,
        handler=_handle_progress_get,
    ),
    "qbaf.node.search": ToolDefinition(
        name="qbaf.node.search",
        description="Search existing nodes in the graph.",
        request_model=NodeSearchRequest,
        response_model=NodeSearchResponse,
        handler=_handle_node_search,
    ),
    "qbaf.node.get": ToolDefinition(
        name="qbaf.node.get",
        description="Fetch a single node with read-only metadata.",
        request_model=NodeGetRequest,
        response_model=NodeGetResponse,
        handler=_handle_node_get,
    ),
    "qbaf.score.get": ToolDefinition(
        name="qbaf.score.get",
        description="Fetch node scores for a batch of node IDs.",
        request_model=ScoreGetRequest,
        response_model=ScoreGetResponse,
        handler=_handle_score_get,
    ),
    "qbaf.explain.local": ToolDefinition(
        name="qbaf.explain.local",
        description="Retrieve top-k local explanations for a node.",
        request_model=ExplainLocalRequest,
        response_model=ExplainLocalResponse,
        handler=_handle_explain_local,
    ),
}


def register(server_app: server.Server, backend: BackendProtocol) -> None:
    """Register list_tools and call_tool handlers for the server."""

    @server_app.list_tools()
    async def list_tools() -> list[types.Tool]:
        tools: list[types.Tool] = []
        for definition in TOOL_DEFINITIONS.values():
            input_schema = definition.request_model.model_json_schema()
            success_schema = definition.response_model.model_json_schema()
            error_schema = ErrorResponse.model_json_schema()

            output_one_of = []
            merged_defs: Dict[str, object] = {}
            for schema in (success_schema, error_schema):
                local_defs = schema.pop("$defs", {})
                merged_defs.update(local_defs)
                output_one_of.append(schema)

            output_schema: Dict[str, object] = {"oneOf": output_one_of}
            if merged_defs:
                output_schema["$defs"] = merged_defs

            tools.append(
                types.Tool(
                    name=definition.name,
                    description=definition.description,
                    inputSchema=input_schema,
                    outputSchema=output_schema,
                )
            )
        return tools

    @server_app.call_tool(validate_input=False)
    async def call_tool(tool_name: str, arguments: Dict[str, object]) -> dict[str, object]:
        definition = TOOL_DEFINITIONS.get(tool_name)
        if definition is None:
            logger.warning("tool_not_found", tool=tool_name)
            error = ErrorResponse(
                error=ErrorEnvelope(
                    code="NOT_FOUND",
                    message=f"Unknown tool: {tool_name}",
                )
            )
            return error.model_dump(mode="json")

        try:
            payload = definition.request_model.model_validate(arguments)
        except ValidationError as exc:
            logger.warning("tool_input_invalid", tool=tool_name, errors=exc.errors())
            error = ErrorResponse(
                error=ErrorEnvelope(
                    code="INVALID_ARGUMENT",
                    message="Invalid tool input",
                    details={"hint": exc.errors()[0]["msg"] if exc.errors() else "validation error"},
                )
            )
            return error.model_dump(mode="json")

        try:
            result = await definition.handler(backend, payload)
        except BackendError as exc:
            logger.warning("backend_error", tool=tool_name, message=str(exc))
            return exc.error.model_dump(mode="json")
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("unexpected_tool_error", tool=tool_name)
            error = ErrorResponse(
                error=ErrorEnvelope(code="INTERNAL", message=str(exc)),
            )
            return error.model_dump(mode="json")

        return result.model_dump(mode="json")


__all__ = ["register"]
