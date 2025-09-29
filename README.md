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
