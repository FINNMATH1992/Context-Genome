from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def pick_env(env: Mapping[str, str], names: list[str], default: str = "") -> tuple[str, str]:
    for name in names:
        value = env.get(name, "").strip()
        if value:
            return value, name
    return default, ""


def runtime_env_summary(env: Mapping[str, str]) -> dict[str, object]:
    api_key, api_source = pick_env(
        env,
        ["CONTEXT_GENOME_LLM_API_KEY", "SKILL_GARDEN_LLM_API_KEY", "OPENAI_API_KEY"],
    )
    model, model_source = pick_env(
        env,
        ["CONTEXT_GENOME_LLM_MODEL", "SKILL_GARDEN_LLM_MODEL", "OPENAI_MODEL"],
    )
    base_url, base_source = pick_env(
        env,
        ["CONTEXT_GENOME_LLM_BASE_URL", "SKILL_GARDEN_LLM_BASE_URL", "OPENAI_BASE_URL"],
        default="https://api.openai.com/v1",
    )
    return {
        "has_api_key": bool(api_key),
        "api_key_source": api_source,
        "model": model,
        "model_source": model_source,
        "base_url": base_url,
        "base_url_source": base_source or "default",
    }


def parse_dotenv_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not (key[0].isalpha() or key[0] == "_"):
            continue
        if not all(ch.isalnum() or ch == "_" for ch in key):
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        values[key] = value
    return values


def merged_env() -> dict[str, str]:
    values: dict[str, str] = {}
    dotenv = ROOT / ".env"
    if dotenv.exists():
        values.update(parse_dotenv_text(dotenv.read_text(encoding="utf-8")))
    values.update(os.environ)
    return values


def default_port(env: Mapping[str, str]) -> int:
    try:
        return int(env.get("CONTEXT_GENOME_PORT", "8765"))
    except ValueError:
        return 8765


def check_python() -> Check:
    version = ".".join(str(part) for part in sys.version_info[:3])
    if sys.version_info >= (3, 11):
        return Check("python", "ok", f"Python {version}")
    return Check("python", "fail", f"Python {version}; Context Genome needs Python 3.11+")


def check_node() -> Check:
    node = shutil.which("node")
    if not node:
        return Check("node", "warn", "node not found; frontend syntax checks will be skipped")
    try:
        result = subprocess.run(
            [node, "--version"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return Check("node", "warn", f"node exists but version check failed: {exc}")
    return Check("node", "ok", result.stdout.strip())


def check_run_script() -> Check:
    path = ROOT / "run.sh"
    if not path.exists():
        return Check("run.sh", "fail", "missing root run.sh")
    if not os.access(path, os.X_OK):
        return Check("run.sh", "fail", "run.sh is not executable")
    return Check("run.sh", "ok", "executable")


def check_port(host: str, port: int) -> Check:
    if port == 0:
        return Check("port", "ok", "port check skipped for dynamic port 0")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            sock.bind((host, port))
    except OSError as exc:
        return Check("port", "warn", f"{host}:{port} is not available ({exc})")
    return Check("port", "ok", f"{host}:{port} is available")


def check_llm(env: Mapping[str, str]) -> list[Check]:
    summary = runtime_env_summary(env)
    checks: list[Check] = []
    if summary["has_api_key"]:
        checks.append(Check("llm api key", "ok", f"set via {summary['api_key_source']}"))
    else:
        checks.append(Check("llm api key", "warn", "not set; you can add it later in Tune -> LLM Runtime"))
    if summary["model"]:
        checks.append(Check("llm model", "ok", f"{summary['model']} via {summary['model_source']}"))
    else:
        checks.append(Check("llm model", "warn", "not set; choose one in Tune -> LLM Runtime"))
    checks.append(Check("llm base url", "ok", f"{summary['base_url']} via {summary['base_url_source']}"))
    return checks


def build_checks(host: str, port: int, env: Mapping[str, str]) -> list[Check]:
    return [
        check_python(),
        check_node(),
        check_run_script(),
        check_port(host, port),
        *check_llm(env),
    ]


def render_text(checks: list[Check]) -> str:
    lines = ["Context Genome doctor"]
    for check in checks:
        marker = {"ok": "OK", "warn": "WARN", "fail": "FAIL"}.get(check.status, check.status.upper())
        lines.append(f"[{marker}] {check.name}: {check.detail}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    env = merged_env()
    parser = argparse.ArgumentParser(description="Check the local Context Genome development environment.")
    parser.add_argument("--host", default=env.get("CONTEXT_GENOME_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=default_port(env))
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    checks = build_checks(args.host, args.port, env)
    if args.json:
        print(json.dumps([check.__dict__ for check in checks], indent=2))
    else:
        print(render_text(checks))
    return 1 if any(check.status == "fail" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
