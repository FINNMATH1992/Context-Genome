from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BLOCKED_PATH_PARTS = {"__pycache__", ".DS_Store"}
BLOCKED_PREFIXES = ("runs/",)
SECRET_PATTERNS = [
    re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}", re.IGNORECASE),
    re.compile(r"BEGIN (RSA|OPENSSH|PRIVATE) KEY"),
    re.compile(r"/Users/[^\s)\\]\"']+"),
]


def main() -> int:
    failures: list[str] = []
    for path in tracked_files():
        rel = path.as_posix()
        parts = set(path.parts)
        if parts & BLOCKED_PATH_PARTS:
            failures.append(f"blocked generated artifact is tracked: {rel}")
            continue
        if rel.startswith(BLOCKED_PREFIXES):
            failures.append(f"runtime export is tracked: {rel}")
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico"}:
            continue
        text = read_text(path)
        if text is None:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                failures.append(f"sensitive pattern {pattern.pattern!r} found in {rel}")

    if failures:
        for failure in failures:
            print(failure)
        return 1
    print("repository hygiene ok")
    return 0


def tracked_files() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return [ROOT / line for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts]


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


if __name__ == "__main__":
    sys.exit(main())
