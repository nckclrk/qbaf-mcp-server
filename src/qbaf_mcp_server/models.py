"""Pydantic models for MCP tool payloads and responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SourceSpan(BaseModel):
    start: int
    end: int


class Source(BaseModel):
    doc_id: str
    url: str | None = None
    span: SourceSpan | None = None


class Claim(BaseModel):
    text: str = Field(min_length=3)
    source: Source | None = None
    canonical: str | None = None
    meta: dict[str, object] | None = None


class SubmitClaimsRequest(BaseModel):
    claims: list[Claim] = Field(min_length=1, max_length=100)
    dedupe: Literal["canonical_exact", "fuzzy"] = "fuzzy"
    client_token: str | None = None


class SubmitClaimsResultItem(BaseModel):
    status: Literal["created", "deduped", "ignored"]
    node_id: str
    reason: str | None = None


class SubmitClaimsResponse(BaseModel):
    graph_id: str
    results: list[SubmitClaimsResultItem]
    ingest_job_id: str | None = None


class ProgressRequest(BaseModel):
    ingest_job_id: str | None = None


class QueueStats(BaseModel):
    pending: int
    inflight: int
    succeeded: int
    failed: int


class RelationMiningStats(BaseModel):
    pending: int
    edges_created: int


class SemanticsStats(BaseModel):
    last_run_at: str | None = None
    converged: bool | None = None
    iters: int | None = None


class Totals(BaseModel):
    nodes: int
    edges: int


class ProgressResponse(BaseModel):
    graph_id: str
    ingest_queue: QueueStats | None = None
    relation_mining: RelationMiningStats | None = None
    semantics: SemanticsStats | None = None
    totals: Totals | None = None


class NodeSearchFilter(BaseModel):
    tags_any: list[str] | None = None


class NodeSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=25, ge=1, le=100)
    filter: NodeSearchFilter | None = None


class NodeSearchHit(BaseModel):
    node_id: str
    text: str
    score: float | None = None


class NodeSearchResponse(BaseModel):
    hits: list[NodeSearchHit]


class NodeGetRequest(BaseModel):
    node_id: str


class NodeWeight(BaseModel):
    mean: float
    std: float


class NodeScore(BaseModel):
    value: float
    semantics: str | None = None
    at: str | None = None


class Node(BaseModel):
    node_id: str
    text: str
    canonical: str | None = None
    weight: NodeWeight | None = None
    score: NodeScore | None = None
    provenance: list[Source] | None = None
    meta: dict[str, object] | None = None


class NodeGetResponse(BaseModel):
    node: Node


class ScoreGetRequest(BaseModel):
    node_ids: list[str]


class NodeScoreValue(BaseModel):
    node_id: str
    value: float


class ScoreGetResponse(BaseModel):
    scores: list[NodeScoreValue]


class ExplainLocalRequest(BaseModel):
    node_id: str
    k: int = Field(default=5, ge=1, le=50)
    mode: Literal["mixed", "support", "attack"] = "mixed"


class ExplainLocalItem(BaseModel):
    from_id: str
    via_edge: str
    type: Literal["support", "attack"]
    marginal_contribution: float


class ExplainLocalResponse(BaseModel):
    node_id: str
    semantics: str | None = None
    top: list[ExplainLocalItem]


class ErrorDetails(BaseModel):
    field: str | None = None
    hint: str | None = None


class ErrorEnvelope(BaseModel):
    code: Literal["INVALID_ARGUMENT", "NOT_FOUND", "CONFLICT", "INTERNAL", "FORBIDDEN"]
    message: str
    details: ErrorDetails | dict[str, object] | None = None


class ErrorResponse(BaseModel):
    error: ErrorEnvelope


__all__ = [
    "Claim",
    "ErrorEnvelope",
    "ErrorResponse",
    "ExplainLocalItem",
    "ExplainLocalRequest",
    "ExplainLocalResponse",
    "Node",
    "NodeGetRequest",
    "NodeGetResponse",
    "NodeScore",
    "NodeScoreValue",
    "NodeSearchFilter",
    "NodeSearchHit",
    "NodeSearchRequest",
    "NodeSearchResponse",
    "ProgressRequest",
    "ProgressResponse",
    "ScoreGetRequest",
    "ScoreGetResponse",
    "Source",
    "SourceSpan",
    "SubmitClaimsRequest",
    "SubmitClaimsResponse",
]
