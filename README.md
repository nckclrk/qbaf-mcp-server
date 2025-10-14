# QBAF MCP Server

Minimal, opinionated Model Context Protocol (MCP) server that gates agent access to a QBAF backend.

## Development

Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Add the source tree to your Python path when running tools locally:

```bash
export PYTHONPATH=src
```

Run tests:

```bash
python -m pytest
```

## Configuration

Runtime settings are loaded from a `.env` file automatically if it exists in the project root. Copy `.env.example` to `.env` and fill in at least the required values before launching the server:

```
GRAPH_ID=your-graph-id
BACKEND_BASE_URL=http://127.0.0.1:8000
# Optional overrides
BACKEND_API_KEY=
TIMEOUT_SECONDS=10
LOG_LEVEL=INFO
# Neo4j-backed service
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

To override a value temporarily, set the environment variable in your shell; explicit environment variables still take precedence over the `.env` file.

## Local Backend (Optional)

For manual testing without a live QBAF deployment, run the built-in Starlette backend:

```bash
source .venv/bin/activate
uvicorn qbaf_mcp_server.dev_backend:app --reload
```

Point `BACKEND_BASE_URL` at the running service (default `http://127.0.0.1:8000`). Once the backend is up you can launch the MCP server through Inspector:

```bash
npx @modelcontextprotocol/inspector python --directory . run python -m qbaf_mcp_server.server
```

## Neo4j Backend Service

To run the persistent backend:

1. Start Neo4j locally (or point to an external instance):
   ```bash
   ./scripts/start_neo4j.sh
   ```
   Set `USE_EXTERNAL_NEO4J=bolt://host:7687` to skip the local container.
2. Populate `.env` with the Neo4j credentials (`NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`).
3. Launch the backend API (from an activated venv):
   ```bash
   PYTHONPATH=src uvicorn qbaf_backend.service:create_app --factory --reload
   ```
   The service listens on `http://127.0.0.1:8000` by default and mirrors the endpoints consumed by the MCP server.

## MCP STDIO Entrypoint

If you need a quiet entry point for tools that communicate with the MCP server over stdio (e.g. Claude Desktop), use:

```bash
./scripts/run_mcp_server.sh
```

The script activates the `.venv` virtual environment (if not already active), exports `PYTHONPATH=src`, and execs `python -m qbaf_mcp_server.server` without printing anything else. Ensure a backend is reachable at the `BACKEND_BASE_URL` defined in your `.env` (the helper above can run the dev backend when needed).
