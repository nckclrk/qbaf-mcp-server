#!/usr/bin/env bash
set -euo pipefail

# Simple helper to start a local Neo4j instance (via Docker) or reuse an external URI.
# Usage:
#   ./scripts/start_neo4j.sh            # launches dockerized Neo4j on localhost
#   USE_EXTERNAL_NEO4J=bolt://host:7687 ./scripts/start_neo4j.sh  # skip docker
#
# Environment variables:
#   NEO4J_CONTAINER       container name (default: qbaf-neo4j)
#   NEO4J_VERSION         image tag (default: 5.22)
#   NEO4J_HTTP_PORT       local HTTP port (default: 7474)
#   NEO4J_BOLT_PORT       local Bolt port (default: 7687)
#   NEO4J_DATA_DIR        persistent data dir (default: .neo4j/data)
#   NEO4J_USERNAME        Neo4j username (default: neo4j)
#   NEO4J_PASSWORD        Neo4j password (default: password)

if [[ -n "${USE_EXTERNAL_NEO4J:-}" ]]; then
  echo "Using external Neo4j at ${USE_EXTERNAL_NEO4J}. No local container started."
  exit 0
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to launch the local Neo4j container." >&2
  exit 1
fi

CONTAINER_NAME="${NEO4J_CONTAINER:-qbaf-neo4j}"
IMAGE_TAG="${NEO4J_VERSION:-5.22}"
HTTP_PORT="${NEO4J_HTTP_PORT:-7474}"
BOLT_PORT="${NEO4J_BOLT_PORT:-7687}"
DATA_DIR="${NEO4J_DATA_DIR:-$(pwd)/.neo4j/data}"
USERNAME="${NEO4J_USERNAME:-neo4j}"
PASSWORD="${NEO4J_PASSWORD:-password}"

mkdir -p "${DATA_DIR}"

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  echo "Neo4j container '${CONTAINER_NAME}' already running."
else
  if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    docker rm -f "${CONTAINER_NAME}" >/dev/null
  fi
  echo "Starting Neo4j container '${CONTAINER_NAME}'..."
  docker run -d \
    --name "${CONTAINER_NAME}" \
    -p "${HTTP_PORT}:7474" \
    -p "${BOLT_PORT}:7687" \
    -e "NEO4J_AUTH=${USERNAME}/${PASSWORD}" \
    -e "NEO4J_PLUGINS=[]" \
    -v "${DATA_DIR}:/data" \
    neo4j:"${IMAGE_TAG}" >/dev/null
fi

echo "Neo4j ready"
echo "  Bolt URI: bolt://localhost:${BOLT_PORT}"
echo "  HTTP UI : http://localhost:${HTTP_PORT}"
echo "Credentials: ${USERNAME}/${PASSWORD}"
