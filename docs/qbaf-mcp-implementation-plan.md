# MCP Server MVP Plan

## Build
1. Bootstrap stdio server (`qbaf_mcp_server.server`) with env-driven config + logging.
2. Implement backend proxy (`backend.py`, `http.py`, `models.py`) with uniform error envelopes.
3. Register six MCP tools and cover them with unit tests.
4. Ship Starlette dev backend (`dev_backend.py`) to unblock manual testing.

## Quality Gates
- `tox -e py312` for unit tests.
- `tox -e lint` for Ruff checks.
- `tox -e type` for mypy.

## Delivery Checklist
- `.env` populated with graph and backend URL.
- README instructions verified (venv, backend, Inspector).
- Release tag `0.1.0` once MCP client smoke test passes.

## Follow-Ups (Post-MVP)
- Add persistence for the dev backend or remove once real backend is wired.
- Expand logging with per-tool timings and request IDs.
- Optional health-check tool for agents.
