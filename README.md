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
