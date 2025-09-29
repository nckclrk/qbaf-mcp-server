"""Neo4j persistence layer for the QBAF service."""

from __future__ import annotations

import asyncio
import json
from typing import List

import ulid
from neo4j import Driver

from qbaf_mcp_server.models import (
    Claim,
    ExplainLocalRequest,
    ExplainLocalResponse,
    Node,
    NodeGetRequest,
    NodeGetResponse,
    NodeScore,
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
    NodeScoreValue,
)


class Neo4jRepository:
    """Wraps basic graph operations backed by Neo4j."""

    def __init__(self, driver: Driver, graph_id: str) -> None:
        self._driver = driver
        self._graph_id = graph_id

    async def submit_claims(self, payload: SubmitClaimsRequest) -> SubmitClaimsResponse:
        return await asyncio.to_thread(self._submit_claims_sync, payload)

    def _submit_claims_sync(self, payload: SubmitClaimsRequest) -> SubmitClaimsResponse:
        results: List[SubmitClaimsResultItem] = []

        def _write(tx) -> None:
            nonlocal results
            results = []
            for claim in payload.claims:
                node_id = str(ulid.new())
                score = self._initial_score(claim)
                tx.run(
                    """
                    CREATE (n:Claim {
                        graph_id: $graph_id,
                        node_id: $node_id,
                        text: $text,
                        canonical: $canonical,
                        meta_json: $meta_json,
                        source_json: $source_json,
                        score: $score
                    })
                    """,
                    graph_id=self._graph_id,
                    node_id=node_id,
                    text=claim.text,
                    canonical=claim.canonical,
                    meta_json=json.dumps(claim.meta) if claim.meta else None,
                    source_json=self._source_json(claim),
                    score=score,
                )
                results.append(SubmitClaimsResultItem(status="created", node_id=node_id))

        with self._driver.session() as session:
            session.execute_write(_write)

        ingest_job_id = str(ulid.new())
        return SubmitClaimsResponse(graph_id=self._graph_id, results=results, ingest_job_id=ingest_job_id)

    async def progress_get(self, _payload: ProgressRequest) -> ProgressResponse:
        return await asyncio.to_thread(self._progress_sync)

    def _progress_sync(self) -> ProgressResponse:
        with self._driver.session() as session:
            record = session.execute_read(
                lambda tx: tx.run(
                    "MATCH (n:Claim {graph_id: $graph_id}) RETURN count(n) AS node_count",
                    graph_id=self._graph_id,
                ).single()
            )
        node_count = record["node_count"] if record else 0
        queue = QueueStats(pending=0, inflight=0, succeeded=node_count, failed=0)
        relation = RelationMiningStats(pending=0, edges_created=0)
        semantics = SemanticsStats(last_run_at=None, converged=True, iters=1)
        totals = Totals(nodes=node_count, edges=0)
        return ProgressResponse(
            graph_id=self._graph_id,
            ingest_queue=queue,
            relation_mining=relation,
            semantics=semantics,
            totals=totals,
        )

    async def node_search(self, payload: NodeSearchRequest) -> NodeSearchResponse:
        return await asyncio.to_thread(self._node_search_sync, payload)

    def _node_search_sync(self, payload: NodeSearchRequest) -> NodeSearchResponse:
        with self._driver.session() as session:
            records = session.execute_read(
                lambda tx: list(
                    tx.run(
                        """
                        MATCH (n:Claim {graph_id: $graph_id})
                        WHERE toLower(n.text) CONTAINS toLower($query)
                        RETURN n.node_id AS node_id, n.text AS text, n.score AS score
                        LIMIT $limit
                        """,
                        graph_id=self._graph_id,
                        query=payload.query,
                        limit=payload.top_k,
                    )
                )
            )
        hits = [
            NodeSearchHit(node_id=record["node_id"], text=record["text"], score=record.get("score"))
            for record in records
        ]
        return NodeSearchResponse(hits=hits)

    async def node_get(self, payload: NodeGetRequest) -> NodeGetResponse | None:
        return await asyncio.to_thread(self._node_get_sync, payload)

    def _node_get_sync(self, payload: NodeGetRequest) -> NodeGetResponse | None:
        with self._driver.session() as session:
            record = session.execute_read(
                lambda tx: tx.run(
                    """
                    MATCH (n:Claim {graph_id: $graph_id, node_id: $node_id})
                    RETURN n.text AS text,
                           n.canonical AS canonical,
                           n.meta_json AS meta_json,
                           n.source_json AS source_json,
                           n.score AS score
                    """,
                    graph_id=self._graph_id,
                    node_id=payload.node_id,
                ).single()
            )
        if record is None:
            return None

        node = Node(
            node_id=payload.node_id,
            text=record["text"],
            canonical=record.get("canonical"),
            meta=self._loads_optional(record.get("meta_json")),
            provenance=self._loads_source(record.get("source_json")),
            score=NodeScore(value=record.get("score", 0.0), semantics="stored"),
        )
        return NodeGetResponse(node=node)

    async def score_get(self, payload: ScoreGetRequest) -> ScoreGetResponse:
        return await asyncio.to_thread(self._score_get_sync, payload)

    def _score_get_sync(self, payload: ScoreGetRequest) -> ScoreGetResponse:
        with self._driver.session() as session:
            records = session.execute_read(
                lambda tx: list(
                    tx.run(
                        """
                        MATCH (n:Claim {graph_id: $graph_id})
                        WHERE n.node_id IN $node_ids
                        RETURN n.node_id AS node_id, coalesce(n.score, 0.0) AS score
                        """,
                        graph_id=self._graph_id,
                        node_ids=payload.node_ids,
                    )
                )
            )
        remaining = set(payload.node_ids)
        scores: list[NodeScoreValue] = []
        for record in records:
            node_id = record["node_id"]
            remaining.discard(node_id)
            scores.append(NodeScoreValue(node_id=node_id, value=record["score"]))
        for missing in remaining:
            scores.append(NodeScoreValue(node_id=missing, value=float("nan")))
        return ScoreGetResponse(scores=scores)

    async def explain_local(self, payload: ExplainLocalRequest) -> ExplainLocalResponse | None:
        # Placeholder: no relationship logic in MVP
        node = await self.node_get(NodeGetRequest(node_id=payload.node_id))
        if node is None:
            return None
        semantics = node.node.score.semantics if node.node.score else None
        return ExplainLocalResponse(node_id=payload.node_id, semantics=semantics, top=[])

    @staticmethod
    def _initial_score(claim: Claim) -> float:
        base = 0.5
        length_bonus = min(len(claim.text) / 200, 0.4)
        return round(base + length_bonus, 3)

    @staticmethod
    def _source_json(claim: Claim) -> str | None:
        if claim.source is None:
            return None
        return json.dumps(claim.source.model_dump(mode="json"))

    @staticmethod
    def _loads_optional(raw: str | None) -> dict[str, object] | None:
        if raw is None:
            return None
        return json.loads(raw)

    @staticmethod
    def _loads_source(raw: str | None) -> list[dict[str, object]] | None:
        if raw is None:
            return None
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        return [data]


# Helper dataclass for typed score results
__all__ = ["Neo4jRepository"]
