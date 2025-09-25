"""Backend integration helpers for the QBAF MCP server."""

from __future__ import annotations

from typing import Any, Dict, Literal, Mapping, Protocol, TypeVar, cast, runtime_checkable

import httpx
from pydantic import BaseModel

from .models import (
    ErrorDetails,
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

ErrorCode = Literal["INVALID_ARGUMENT", "NOT_FOUND", "CONFLICT", "INTERNAL", "FORBIDDEN"]

T = TypeVar("T", bound=BaseModel)

STATUS_TO_ERROR: Mapping[int, ErrorCode] = {
    400: "INVALID_ARGUMENT",
    401: "FORBIDDEN",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
}

ERROR_CODES: set[str] = set(STATUS_TO_ERROR.values()) | {"INTERNAL"}


@runtime_checkable
class BackendProtocol(Protocol):
    async def submit_claims(self, payload: SubmitClaimsRequest) -> SubmitClaimsResponse: ...

    async def progress_get(self, payload: ProgressRequest) -> ProgressResponse: ...

    async def node_search(self, payload: NodeSearchRequest) -> NodeSearchResponse: ...

    async def node_get(self, payload: NodeGetRequest) -> NodeGetResponse: ...

    async def score_get(self, payload: ScoreGetRequest) -> ScoreGetResponse: ...

    async def explain_local(self, payload: ExplainLocalRequest) -> ExplainLocalResponse: ...


class BackendError(RuntimeError):
    """Wraps errors returned from the backend service."""

    def __init__(self, error: ErrorResponse) -> None:
        super().__init__(error.error.message)
        self.error = error


class BackendClient(BackendProtocol):
    def __init__(self, client: httpx.AsyncClient, graph_id: str) -> None:
        self._client = client
        self._graph_id = graph_id

    async def submit_claims(self, payload: SubmitClaimsRequest) -> SubmitClaimsResponse:
        request_json = payload.model_dump(mode="json")
        request_json["graph_id"] = self._graph_id
        response = await self._client.post("/ingest/claims", json=request_json)
        return self._parse_response(response, SubmitClaimsResponse)

    async def progress_get(self, payload: ProgressRequest) -> ProgressResponse:
        params: Dict[str, Any] = {"graph_id": self._graph_id}
        if payload.ingest_job_id:
            params["job_id"] = payload.ingest_job_id
        response = await self._client.get("/progress", params=params)
        return self._parse_response(response, ProgressResponse)

    async def node_search(self, payload: NodeSearchRequest) -> NodeSearchResponse:
        params: Dict[str, Any] = {
            "graph_id": self._graph_id,
            "q": payload.query,
            "k": payload.top_k,
        }
        if payload.filter and payload.filter.tags_any:
            params["tags"] = ",".join(payload.filter.tags_any)
        response = await self._client.get("/nodes/search", params=params)
        return self._parse_response(response, NodeSearchResponse)

    async def node_get(self, payload: NodeGetRequest) -> NodeGetResponse:
        params = {"graph_id": self._graph_id}
        response = await self._client.get(f"/nodes/{payload.node_id}", params=params)
        return self._parse_response(response, NodeGetResponse)

    async def score_get(self, payload: ScoreGetRequest) -> ScoreGetResponse:
        request_json = {
            "graph_id": self._graph_id,
            "node_ids": payload.node_ids,
        }
        response = await self._client.post("/scores/batch", json=request_json)
        return self._parse_response(response, ScoreGetResponse)

    async def explain_local(self, payload: ExplainLocalRequest) -> ExplainLocalResponse:
        params: Dict[str, Any] = {
            "graph_id": self._graph_id,
            "node_id": payload.node_id,
            "k": payload.k,
            "mode": payload.mode,
        }
        response = await self._client.get("/explain/local", params=params)
        return self._parse_response(response, ExplainLocalResponse)

    def _parse_response(self, response: httpx.Response, model_type: type[T]) -> T:
        if response.status_code >= 400:
            raise BackendError(self._translate_error(response))
        try:
            data = response.json()
        except ValueError as exc:  # pragma: no cover - backend contract violation
            raise BackendError(
                ErrorResponse(
                    error=ErrorEnvelope(
                        code="INTERNAL",
                        message="Backend returned invalid JSON",
                    )
                )
            ) from exc
        return model_type.model_validate(data)

    def _translate_error(self, response: httpx.Response) -> ErrorResponse:
        default_code = cast(ErrorCode, STATUS_TO_ERROR.get(response.status_code, "INTERNAL"))
        try:
            payload = response.json()
        except ValueError:
            return ErrorResponse(
                error=ErrorEnvelope(
                    code=default_code,
                    message=f"Backend returned invalid JSON (status {response.status_code})",
                )
            )

        if "error" in payload:
            error_payload = payload["error"]
            code = self._normalize_error_code(error_payload.get("code"), default_code)
            message = error_payload.get("message", "backend error")
            details_raw = error_payload.get("details")
            details = _coerce_error_details(details_raw)
            return ErrorResponse(
                error=ErrorEnvelope(
                    code=code,
                    message=message,
                    details=details,
                )
            )

        message = payload.get("message") or f"Backend returned status {response.status_code}"
        details = _coerce_error_details(payload.get("details"))
        return ErrorResponse(
            error=ErrorEnvelope(
                code=default_code,
                message=message,
                details=details,
            )
        )

    @staticmethod
    def _normalize_error_code(code: object, default: ErrorCode) -> ErrorCode:
        if isinstance(code, str) and code in ERROR_CODES:
            return cast(ErrorCode, code)
        return default


def _coerce_error_details(details: object) -> ErrorDetails | dict[str, object] | None:
    if details is None:
        return None
    if isinstance(details, dict):
        try:
            return ErrorDetails.model_validate(details)
        except ValueError:
            return details
    return None


__all__ = ["BackendClient", "BackendError", "BackendProtocol"]
