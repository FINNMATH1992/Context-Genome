#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$ROOT_DIR"

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
