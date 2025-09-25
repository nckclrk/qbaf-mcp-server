# QBAF MCP Server (Python) — Design Document

## 1. Purpose and Scope
The QBAF MCP server provides a minimal, opinionated interface for agents to submit claims into a preconfigured argumentation graph and to inspect read-only state about graph progress, nodes, scores, and local explanations. The server acts as a schema-enforcing proxy in front of existing backend workers that manage graph lifecycle, relation inference, and semantics computation. Its primary goals are to expose the smallest useful surface for agents, guarantee invariants about write operations, and keep operational complexity low.

## 2. Goals and Non-Goals
- **Goals**
  - Accept idempotent claim submissions for a single, server-configured graph.
  - Provide read-only tools for progress monitoring, node lookup, score retrieval, and local explanations.
  - Enforce strict validation and scope controls so agents cannot mutate graphs, edges, or scores outside claim ingestion.
  - Offer predictable JSON contracts with uniform error envelopes and structured logging for downstream observability.
  - Remain lightweight to deploy, package, and operate.
- **Non-Goals**
  - Managing graph creation, deletion, or configuration beyond selecting a fixed `GRAPH_ID` at startup.
  - Producing edges, semantics, or scores directly; those belong to backend workers.
  - Serving as a general-purpose QBAF API gateway; this surface is opinionated for agent workflows only.
  - Supporting multi-graph tenancy or per-agent authorization policies beyond what backend workers already enforce.

## 3. System Context
- **Upstream clients**: MCP-compatible agents (CLI, IDE, autonomous orchestrators) communicating over stdio transport.
- **Server**: Python process hosting MCP tools (using the official `mcp` SDK) and async HTTP proxy logic.
- **Backend services**: Existing QBAF worker APIs responsible for ingestion, progress tracking, search, scoring, and explanations.
- **Observability sinks**: Structured logs (JSON via `structlog`) shipped to centralized logging; metrics and traces can be added later via adapters.

```
Agents (MCP clients)
        |
        v
QBAF MCP Server (Python, stdio transport)
        |
        v
QBAF Backend HTTP APIs (ingest, progress, nodes, scores, explain)
```

## 4. High-Level Architecture
- **Transport Layer**: The MCP `Server` handles registration of six tools and executes them on incoming agent requests. Communication occurs over stdio, allowing embedding into orchestrators without network exposure.
- **Validation Layer**: Inputs are parsed with Pydantic models to guarantee schema compliance, enforce field constraints (lengths, enums), and sanitize metadata before forwarding.
- **Proxy Layer**: Each tool calls the backend via an `httpx.AsyncClient` configured with base URL, API key headers, and timeouts. Responses are normalized to the expected JSON envelopes before returning to the agent.
- **State Management**: The server is mostly stateless beyond holding configuration and an `AsyncClient` instance. Idempotency is enforced per request using caller-supplied `client_token` or server-generated ULIDs.
- **Error Handling**: Backend failures or validation errors are mapped to a uniform `{ "error": { ... } }` envelope with standardized codes.

## 5. Tool Surface Summary
| Tool | Verb | Backend Endpoint | Notes |
| --- | --- | --- | --- |
| `qbaf.claim.submit` | POST | `POST /ingest/claims` | Only write path; injects fixed `graph_id`; honors `client_token`.
| `qbaf.progress.get` | GET | `GET /progress` | Optional `ingest_job_id` query arg; returns queue, mining, semantics rollups.
| `qbaf.node.search` | GET | `GET /nodes/search` | Supports text query, `top_k`, and simple tag filter projection.
| `qbaf.node.get` | GET | `GET /nodes/{node_id}` | Returns canonical node payload with scores and provenance.
| `qbaf.score.get` | POST | `POST /scores/batch` | Fetches score values for provided node IDs.
| `qbaf.explain.local` | GET | `GET /explain/local` | Retrieves top-k contributors filtered by mode (mixed/support/attack).

## 6. Data Contracts
- **Request validation**
  - `Claim` objects enforce minimum text length, optional canonical text, metadata dictionary allowance, and typed provenance references.
  - Enum-like fields (`dedupe`, `mode`) use regex or literal constraints to block unexpected values.
  - Numeric bounds (e.g., `top_k`, `k`) default to safe ranges (e.g., 1–100) with server-side caps to prevent backend abuse.
- **Response shaping**
  - Datasets returned by backend are passed through mostly verbatim but subjected to key renaming or field pruning if necessary to maintain stable contracts.
  - Error codes map backend HTTP status to MCP error codes (`INVALID_ARGUMENT`, `NOT_FOUND`, `CONFLICT`, `INTERNAL`). Unexpected backend payloads trigger `INTERNAL` with diagnostic hints.

## 7. Configuration and Secrets
- Environment variables configure runtime behavior:
  - `GRAPH_ID` (required): immutable identifier applied to every backend call.
  - `BACKEND_BASE_URL` (required): root endpoint for worker APIs.
  - `BACKEND_API_KEY` (optional): bearer token for backend requests.
  - `TIMEOUT_SECONDS` (optional, default 10): request timeout.
  - `LOG_LEVEL` (optional, default INFO): structlog log level.
- Configuration is loaded once at startup, with validation and fail-fast behavior. Secrets (API keys) never log.

## 8. Logging, Metrics, and Tracing
- **Logging**: `structlog` configured for JSON output, including fields such as `tool`, `graph_id`, `status_code`, `latency_ms`, and `error_code` when applicable.
- **Metrics**: Provide hook points for future integration (e.g., optional Prometheus counters for tool invocations, backend error rates). Initial version logs metrics-like fields for external scraping.
- **Tracing**: Propagate correlation IDs by forwarding `client_token` (when provided) to backend headers; optionally generate internal request IDs via ULID and include in logs.

## 9. Concurrency, Retry, and Backpressure
- The MCP server processes tool calls concurrently via the async event loop. `httpx.AsyncClient` reuses connections and respects configured timeouts.
- Automatic retries are not applied by default to avoid duplicate writes; idempotency keys mitigate agent retries.
- Backend `202` responses indicating queue backpressure include `ingest_job_id`; clients are advised via documentation to poll `qbaf.progress.get`.

## 10. Security and Compliance Considerations
- Enforce HTTPS-only backend URLs in production by validating `BACKEND_BASE_URL` at startup.
- Restrict write surface to claims; detect attempts to include score/edge fields and respond with `FORBIDDEN` hints.
- Protect against large payloads by capping claim batch size (e.g., 100 claims) and overall request body size.
- Sanitize and pass through provenance carefully; optionally redact sensitive metadata before returning to agents if backend policies require.

## 11. Deployment and Runtime
- Distributed as a standalone Python package (e.g., via `uv` or `pipx`) or container image.
- Suggested entry point: `python -m qbaf_mcp_server` launching `server.run_stdio()`.
- Container image can be minimal (e.g., `python:3.12-slim`) with non-root user, read-only filesystem, and environment-driven config.

## 12. Testing Strategy
- **Unit tests**: Validate Pydantic schemas, enum constraints, and error mapping logic.
- **Integration tests**: Use `httpx.MockTransport` or lightweight `respx` fixtures to simulate backend responses for each tool path, ensuring contract compatibility.
- **Contract tests**: Optionally run against a staging backend to detect drift in upstream APIs.
- **Linting/typing**: `ruff` for lint, `mypy` (strict-ish) for type safety.

## 13. Operational Runbooks
- **Startup**: Validate environment, log configuration, warm up backend health check (`GET /progress`).
- **Health monitoring**: Because MCP servers run over stdio, embed keepalive logs and optionally implement a synthetic `qbaf.health.check` tool (future enhancement).
- **Failure handling**: On repeated backend failures, surface `INTERNAL` errors with hints; rely on orchestrator supervision to restart the process.

## 14. Future Enhancements (Out of Scope Now)
- Multi-graph support with per-agent ACLs.
- Streaming progress updates or subscriptions instead of polling.
- Tooling for bulk export/import of graph data.
- Built-in rate limiting per agent session.

## 15. Open Questions
- Should provenance be redacted or filtered before returning to agents? Requirements depend on downstream privacy policies.
- Do backend endpoints guarantee backward-compatible schemas, or is a version negotiation layer required?
- What observability stack will consume structlog JSON output, and are additional sinks needed?
- Are there compliance requirements (PII, audit logs) that demand additional logging or access controls beyond API key enforcement?
