#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage: ./run.sh [server options]

Starts the Context Genome browser observer.

Defaults:
  host: 127.0.0.1
  port: 8765

Environment:
  CONTEXT_GENOME_HOST
  CONTEXT_GENOME_PORT
  CONTEXT_GENOME_LLM_API_KEY
  CONTEXT_GENOME_LLM_MODEL
  CONTEXT_GENOME_LLM_BASE_URL
  CONTEXT_GENOME_LLM_JSON_MODE
  CONTEXT_GENOME_LLM_DISABLE_THINKING

The script also reads .env if present. Shell environment variables take
priority over .env. Common OPENAI_* and legacy SKILL_GARDEN_LLM_* names are
mapped into CONTEXT_GENOME_LLM_* for the launched server process.

Examples:
  ./run.sh
  ./run.sh --port 8777
  CONTEXT_GENOME_HOST=0.0.0.0 CONTEXT_GENOME_PORT=8765 ./run.sh
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

load_dotenv() {
  [[ -f ".env" ]] || return 0
  local line key value
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "${line//[[:space:]]/}" || "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || continue
    key="${BASH_REMATCH[1]}"
    value="${BASH_REMATCH[2]}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"
    if [[ "${value:0:1}" == "\"" && "${value: -1}" == "\"" ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "${value:0:1}" == "'" && "${value: -1}" == "'" ]]; then
      value="${value:1:${#value}-2}"
    fi
    if [[ -z "${!key+x}" ]]; then
      export "$key=$value"
    fi
  done < ".env"
}

load_dotenv

HOST="${CONTEXT_GENOME_HOST:-127.0.0.1}"
PORT="${CONTEXT_GENOME_PORT:-8765}"
PYTHON_BIN="${PYTHON:-python}"

# Normalize common OpenAI-compatible environment names into the project namespace.
# Nothing is printed, and API keys remain only in this process environment.
if [[ -z "${CONTEXT_GENOME_LLM_API_KEY:-}" ]]; then
  if [[ -n "${SKILL_GARDEN_LLM_API_KEY:-}" ]]; then
    export CONTEXT_GENOME_LLM_API_KEY="$SKILL_GARDEN_LLM_API_KEY"
  elif [[ -n "${OPENAI_API_KEY:-}" ]]; then
    export CONTEXT_GENOME_LLM_API_KEY="$OPENAI_API_KEY"
  fi
fi

if [[ -z "${CONTEXT_GENOME_LLM_MODEL:-}" ]]; then
  if [[ -n "${SKILL_GARDEN_LLM_MODEL:-}" ]]; then
    export CONTEXT_GENOME_LLM_MODEL="$SKILL_GARDEN_LLM_MODEL"
  elif [[ -n "${OPENAI_MODEL:-}" ]]; then
    export CONTEXT_GENOME_LLM_MODEL="$OPENAI_MODEL"
  fi
fi

if [[ -z "${CONTEXT_GENOME_LLM_BASE_URL:-}" ]]; then
  if [[ -n "${SKILL_GARDEN_LLM_BASE_URL:-}" ]]; then
    export CONTEXT_GENOME_LLM_BASE_URL="$SKILL_GARDEN_LLM_BASE_URL"
  elif [[ -n "${OPENAI_BASE_URL:-}" ]]; then
    export CONTEXT_GENOME_LLM_BASE_URL="$OPENAI_BASE_URL"
  fi
fi

if [[ -z "${CONTEXT_GENOME_LLM_JSON_MODE:-}" && -n "${SKILL_GARDEN_LLM_JSON_MODE:-}" ]]; then
  export CONTEXT_GENOME_LLM_JSON_MODE="$SKILL_GARDEN_LLM_JSON_MODE"
fi

if [[ -z "${CONTEXT_GENOME_LLM_DISABLE_THINKING:-}" && -n "${SKILL_GARDEN_LLM_DISABLE_THINKING:-}" ]]; then
  export CONTEXT_GENOME_LLM_DISABLE_THINKING="$SKILL_GARDEN_LLM_DISABLE_THINKING"
fi

exec "$PYTHON_BIN" -B -m context_genome.server --host "$HOST" --port "$PORT" "$@"
