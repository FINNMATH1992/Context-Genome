from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from context_genome.engine.models import Action, Coord


ALLOWED_ACTIONS = {
    "read",
    "scan",
    "reflect",
    "write",
    "copy",
    "move",
    "steal",
    "delete",
    "harvest",
    "repair",
    "protect",
    "wait",
}


@dataclass
class ActionParseResult:
    action: Action
    ok: bool
    error: str = ""
    raw: str = ""


def parse_action_text(actor_id: str, raw_text: str) -> ActionParseResult:
    raw = raw_text.strip()
    try:
        payload = json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError as exc:
        return _failed(actor_id, raw, f"invalid JSON: {exc.msg}")

    if not isinstance(payload, dict):
        return _failed(actor_id, raw, "top-level value must be an object")

    action_name = str(payload.get("action") or "wait").strip().lower()
    if action_name not in ALLOWED_ACTIONS:
        return _failed(actor_id, raw, f"unknown action {action_name!r}")

    try:
        energy_bid = max(0.0, float(payload.get("energy_bid") or 0.0))
    except (TypeError, ValueError):
        energy_bid = 0.0

    result = Action(
        actor_id=actor_id,
        action=action_name,
        energy_bid=energy_bid,
        source=_optional_str(payload.get("source")),
        target=_optional_str(payload.get("target")),
        target_cell=_parse_coord(payload.get("target_cell")),
        resource=_optional_str(payload.get("resource")),
        payload=str(payload.get("payload") or "")[:4096],
        mode=str(payload.get("mode") or "append"),
        note=str(payload.get("note") or "")[:240],
    )
    return ActionParseResult(action=result, ok=True, raw=raw)


def _failed(actor_id: str, raw: str, error: str) -> ActionParseResult:
    return ActionParseResult(
        action=Action(actor_id=actor_id, action="wait", energy_bid=0, note=f"parse failure: {error}"),
        ok=False,
        error=error,
        raw=raw,
    )


def _strip_code_fence(raw: str) -> str:
    if not raw.startswith("```"):
        return raw
    lines = raw.splitlines()
    if len(lines) >= 3 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return raw


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_coord(value: Any) -> Optional[Coord]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        return (int(value[0]), int(value[1]))
    except (TypeError, ValueError):
        return None
