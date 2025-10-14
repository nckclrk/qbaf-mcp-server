#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

VENV_DIR="${VENV_DIR_OVERRIDE:-${ROOT_DIR}/.venv}"

if [[ -n "${VIRTUAL_ENV:-}" ]]; then
  ACTIVE_VENV="${VIRTUAL_ENV}"
else
  ACTIVE_VENV="${VENV_DIR}"
  if [[ ! -d "${ACTIVE_VENV}" ]]; then
    printf 'Virtual environment not found at %s\n' "${ACTIVE_VENV}" >&2
    exit 1
  fi
  if [[ ! -f "${ACTIVE_VENV}/bin/activate" ]]; then
    printf 'Activate script missing in %s/bin/activate\n' "${ACTIVE_VENV}" >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  source "${ACTIVE_VENV}/bin/activate"
fi

PYTHON_BIN="${PYTHON:-python}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  PYTHON_BIN="python3"
fi
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  printf 'Python interpreter not found in PATH.\n' >&2
  exit 1
fi

export PYTHONPATH="${ROOT_DIR}/src${PYTHONPATH:+:${PYTHONPATH}}"

exec "${PYTHON_BIN}" -m qbaf_mcp_server.server
