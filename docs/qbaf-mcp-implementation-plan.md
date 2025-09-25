# QBAF MCP Server — Implementation Plan

## 1. Assumptions and Dependencies
- Backend HTTP endpoints (`/ingest/claims`, `/progress`, `/nodes/search`, `/nodes/{id}`, `/scores/batch`, `/explain/local`) exist and are reachable in staging.
- MCP Python SDK (`mcp`) and required libraries (`httpx`, `pydantic>=2`, `structlog`, `orjson`, `ulid-py`) are available in the target runtime.
- Development flow uses Python 3.12, `uv` or `pip-tools` for dependency locking, and GitHub Actions (or similar) for CI.
- Network access to backend is secured with API key authentication; secrets management (e.g., Doppler, Vault) supplies environment variables at runtime.

## 2. Milestones Overview
1. **Foundation & Scaffolding (Week 1)**
2. **Core Tool Implementations (Week 2)**
3. **Observability & Validation Hardening (Week 3)**
4. **Integration & QA (Week 4)**
5. **Release Preparation (Week 5)**

Time boxes assume one senior engineer (~50% allocation). Adjust durations if more contributors join.

## 3. Detailed Work Breakdown

### Milestone 1 — Foundation & Scaffolding (Week 1)
- Initialize repository structure (`src/`, `tests/`, `docs/`, `pyproject.toml`).
- Set up tooling: formatter (`ruff`), type checker (`mypy`), task runner (`tox` or `nox`), `pre-commit` hooks.
- Define base config loader with environment validation and defaults.
- Create `AsyncClient` factory with timeout, headers, and health check utility.
- Acceptance: basic `server.run_stdio()` starts with configuration loaded; unit tests cover config errors.

### Milestone 2 — Core Tool Implementations (Week 2)
- Implement Pydantic schemas for claims, progress requests, node filters, scores, explanations.
- Register MCP tools with input parsing, backend invocation, and response normalization.
- Ensure `qbaf.claim.submit` supports server-generated ULID for missing `client_token`.
- Implement uniform error mapping and raise on unexpected backend payloads.
- Acceptance: local integration tests with mocked backend covering success and error flows per tool.

### Milestone 3 — Observability & Validation Hardening (Week 3)
- Integrate `structlog` with contextual middleware (tool name, graph_id, request_id).
- Add request/response size limits, batch size enforcement, and standard latency metrics (log fields or optional Prometheus exporter).
- Implement optional correlation ID propagation (HTTP header) using `client_token` or generated ULID.
- Acceptance: logs emit structured events; tests verify validation rejects out-of-bounds payloads.

### Milestone 4 — Integration & QA (Week 4)
- Stand up staging pipeline pointing to backend sandbox; run contract tests via mocked responses and live smoke tests.
- Document runbooks, tool usage examples, and troubleshooting steps in `docs/`.
- Conduct failure mode testing (timeouts, 4xx/5xx responses, malformed payloads) to validate error envelope consistency.
- Acceptance: staging report with pass/fail matrix; documentation updated with findings.

### Milestone 5 — Release Preparation (Week 5)
- Finalize versioning scheme (`0.1.0`), changelog, and release notes.
- Build container image and publish to registry (if required).
- Set up CI pipeline for lint, type check, tests, and container build.
- Provide delivery checklist (env vars, secrets, deployment steps) to operations.
- Acceptance: CI green, artifact published, hand-off meeting complete.

## 4. Testing Matrix
| Layer | Tools | Responsibility |
| --- | --- | --- |
| Unit | `pytest`, `pydantic` validators, schema fixtures | Engineering |
| Integration | `pytest` + `httpx.MockTransport` / `respx`, asynchronous context tests | Engineering |
| Contract | Live staging hits with sanitized data | Engineering + QA |
| Regression | Automated via CI on every merge | Engineering |

## 5. Risk Register
- **Backend contract drift**: Mitigate with nightly contract tests; add version pinning headers if backend supports.
- **Throughput spikes**: Enforce batch caps and timeouts; monitor logs for saturation cues.
- **Agent misuse**: Document error responses; consider future rate limiting or auth layers.
- **Dependency updates**: Lock versions, run dependabot weekly, ensure reproducible builds.

## 6. Communication & Collaboration
- Weekly sync to review milestone status and unblock dependencies.
- Async updates via issue tracker; each milestone tracked as an epic with linked tasks.
- Maintain `docs/changelog.md` for incremental changes and key decisions.

## 7. Deliverables Checklist
- Source code in `src/qbaf_mcp_server/` with tests and docs.
- `docs/` containing design, usage guide, and runbook.
- Automated CI pipeline configuration.
- Container image or installable package artifact.
- Release notes and operations hand-off materials.

## 8. Post-Release Follow-Ups
- Monitor logs for error rate >1% during first week; raise incident if breached.
- Collect agent feedback on tool ergonomics and iterate on documentation.
- Evaluate feasibility of optional features (health check tool, multi-graph) after stabilization.
