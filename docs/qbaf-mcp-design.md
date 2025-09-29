# QBAF MCP Server — MVP Design

## Objective
- Single MCP server that proxies a fixed QBAF graph over stdio.
- Six tools exposed: claim submit, progress get, node search, node get, score get, explain local.

## Components
- `qbaf_mcp_server.server`: loads `.env`, bootstraps stdio transport, registers tools.
- `qbaf_mcp_server.backend`: async proxy to the configured HTTP backend.
- `qbaf_mcp_server.dev_backend`: Starlette app for local testing (`uvicorn qbaf_mcp_server.dev_backend:app`).
- `qbaf_mcp_server.tools`: maps tool names to backend calls and shared error handling.

## Backend Contracts (HTTP)
| Endpoint | Method | Notes |
| --- | --- | --- |
| `/ingest/claims` | POST | body `{graph_id, claims[], ...}` → results + ingest_job_id |
| `/progress` | GET | query `graph_id`, optional `job_id`; returns ingest/semantics totals |
| `/nodes/search` | GET | query `graph_id`, `q`, optional `k`, `tags` |
| `/nodes/{id}` | GET | query `graph_id`; returns node payload |
| `/scores/batch` | POST | body `{graph_id, node_ids[]}` |
| `/explain/local` | GET | query `graph_id`, `node_id`, optional `k`, `mode` |

All errors should return `{"error": {"code", "message"}}` with HTTP status ≥400.

## Configuration
| Variable | Purpose | Default |
| --- | --- | --- |
| `GRAPH_ID` | Required graph identifier | – |
| `BACKEND_BASE_URL` | Base URL for backend (`http://127.0.0.1:8000` for dev) | – |
| `BACKEND_API_KEY` | Optional bearer token | empty |
| `TIMEOUT_SECONDS` | HTTP timeout | `10` |
| `LOG_LEVEL` | Structlog level | `INFO` |

## Local Dev Loop
1. `uvicorn qbaf_mcp_server.dev_backend:app` (optional).
2. `npx @modelcontextprotocol/inspector python --directory . run python -m qbaf_mcp_server.server`.
3. Exercise tools via Inspector UI or your MCP client.
