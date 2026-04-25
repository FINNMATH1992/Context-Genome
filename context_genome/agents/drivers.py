from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request
from hashlib import sha1
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Protocol, Tuple

from context_genome.engine.models import Action, Organism, VFile

from .action_parser import parse_action_text
from .prompt_builder import build_action_messages, build_action_prompt

if TYPE_CHECKING:
    from context_genome.engine.world import ContextGenomeWorld


class AgentDriver(Protocol):
    mode: str
    label: str

    def decide(self, world: "ContextGenomeWorld", org: Organism, observation: Dict) -> Action:
        ...


@dataclass
class RuleAgentDriver:
    mode: str = "rule"
    label: str = "Rule agent"

    def decide(self, world: "ContextGenomeWorld", org: Organism, observation: Dict) -> Action:
        from context_genome.engine import rule_agent

        return rule_agent.decide(world, org, observation)


@dataclass
class JsonRuleAgentDriver:
    mode: str = "json_rule"
    label: str = "JSON rule agent"

    def decide(self, world: "ContextGenomeWorld", org: Organism, observation: Dict) -> Action:
        from context_genome.engine import rule_agent

        proposed = rule_agent.decide(world, org, observation)
        raw = json.dumps(_action_for_wire(proposed), ensure_ascii=False)
        parsed = parse_action_text(org.org_id, raw)
        if not parsed.ok:
            _record_parse_failure(world, org, parsed.raw, parsed.error)
        return parsed.action


@dataclass
class PassiveAgentDriver:
    mode: str = "passive"
    label: str = "Passive control"

    def decide(self, world: "ContextGenomeWorld", org: Organism, observation: Dict) -> Action:
        return Action(actor_id=org.org_id, action="wait", energy_bid=0, note="passive control")


@dataclass
class PromptPreviewDriver:
    mode: str = "prompt_preview"
    label: str = "Prompt preview"

    def decide(self, world: "ContextGenomeWorld", org: Organism, observation: Dict) -> Action:
        skill_policy = _skill_prompt_policy(org)
        messages = build_action_messages(
            org.skill_text(),
            observation,
            _file_content(org, "memory.md"),
            _load_dialogue_messages(org),
            skill_policy,
        )
        _write_virtual_file(org, "last_prompt.txt", json.dumps(messages, ensure_ascii=False, indent=2)[:16_384])
        return Action(actor_id=org.org_id, action="wait", energy_bid=0, note="prompt preview")


@dataclass
class OpenAICompatibleDriver:
    mode: str = "llm_json"
    label: str = "LLM JSON"

    def decide(self, world: "ContextGenomeWorld", org: Organism, observation: Dict) -> Action:
        return _rule_fallback(world, org, observation, "llm batch unavailable")

    def start_batch(self, world: "ContextGenomeWorld", scheduled: List[Tuple[Organism, Dict]]) -> "LLMBatch":
        runtime = _llm_runtime(world.config.llm_model)
        if not runtime["configured"]:
            if getattr(world, "llm_missing_config_reported_tick", -1) != world.tick:
                world.llm_missing_config_reported_tick = world.tick
                world.record_event(
                    "llm",
                    "LLM driver is not configured; falling back to rule-agent",
                    actor_id=scheduled[0][0].org_id if scheduled else None,
                    severity="warn",
                    data={"missing": runtime["missing"]},
                )
            return LLMBatch(
                submitted_tick=world.tick,
                items=[
                    LLMBatchItem(
                        org_id=org.org_id,
                        fallback=_rule_fallback(world, org, observation, "llm not configured"),
                    )
                    for org, observation in scheduled
                ],
            )

        max_calls = max(0, int(world.config.max_llm_calls_per_tick))
        scheduled = _order_bound_llm_schedule(scheduled)
        items: List[LLMBatchItem] = []
        for index, (org, observation) in enumerate(scheduled):
            fallback = _rule_fallback(world, org, observation, "llm batch fallback")
            if index >= max_calls:
                fallback.note = "waiting for bound llm turn; rule fallback"
                items.append(LLMBatchItem(org_id=org.org_id, fallback=fallback))
                continue

            skill_policy = _skill_prompt_policy(org)
            messages = build_action_messages(
                org.skill_text(),
                observation,
                _file_content(org, "memory.md"),
                _load_dialogue_messages(org),
                skill_policy,
            )
            current_user = messages[-1]["content"]
            _write_virtual_file(org, "last_prompt.txt", json.dumps(messages, ensure_ascii=False, indent=2)[:16_384])
            future = _LLM_EXECUTOR.submit(
                _call_chat_completion,
                messages,
                runtime,
                float(world.config.llm_temperature),
                int(world.config.llm_max_tokens),
                float(world.config.llm_timeout_seconds),
            )
            items.append(
                LLMBatchItem(
                    org_id=org.org_id,
                    fallback=fallback,
                    future=future,
                    model=runtime["model"],
                    user_message=current_user,
                    dialogue_user_message=_dialogue_observation_summary(world, org, observation, skill_policy),
                    skill_hash=str(skill_policy.get("hash") or ""),
                )
            )

        world.llm_calls_this_tick = sum(1 for item in items if item.future is not None)
        world.record_event(
            "llm",
            f"submitted {world.llm_calls_this_tick} LLM request(s) for batch decision",
            data={
                "model": runtime["model"],
                "scheduled": len(scheduled),
                "submitted": world.llm_calls_this_tick,
                "scheduler": "bound_round_robin",
            },
        )
        return LLMBatch(submitted_tick=world.tick, items=items)

    def batch_ready(self, batch: "LLMBatch") -> bool:
        return all(item.future is None or item.future.done() for item in batch.items)

    def finish_batch(self, world: "ContextGenomeWorld", batch: "LLMBatch") -> List[Action]:
        actions: List[Action] = []
        for item in batch.items:
            org = world.orgs.get(item.org_id)
            if org is None:
                continue
            if item.future is None:
                actions.append(item.fallback)
                continue
            actions.append(_consume_llm_result(world, org, item, batch.submitted_tick))
        return actions

    def cancel_batch(self, batch: "LLMBatch") -> None:
        for item in batch.items:
            if item.future is not None and not item.future.done():
                item.future.cancel()


class LLMDriverError(RuntimeError):
    pass


@dataclass
class LLMResult:
    content: str
    usage: Dict[str, int | bool]


@dataclass
class LLMBatchItem:
    org_id: str
    fallback: Action
    future: Future | None = None
    model: str = ""
    user_message: str = ""
    dialogue_user_message: str = ""
    skill_hash: str = ""


@dataclass
class LLMBatch:
    submitted_tick: int
    items: List[LLMBatchItem]

    def pending_count(self) -> int:
        return sum(1 for item in self.items if item.future is not None and not item.future.done())


_LLM_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="skill-garden-llm")
_RUNTIME_OVERRIDE_LOCK = threading.RLock()
_RUNTIME_OVERRIDES: Dict[str, str] = {}
PROMPT_STATE_FILE = "prompt_state.json"
DIALOGUE_HISTORY_LIMIT = 16
DIALOGUE_CONTENT_LIMIT = 4096


AGENT_MODES = {
    "rule": {"label": "Rule agent", "description": "Direct deterministic rule-agent actions."},
    "json_rule": {"label": "JSON rule agent", "description": "Rule actions serialized and parsed as strict JSON."},
    "llm_json": {"label": "LLM JSON", "description": "Batch OpenAI-compatible chat completions, then simultaneous actions."},
    "passive": {"label": "Passive control", "description": "Organisms only wait; useful as a decay control."},
    "prompt_preview": {"label": "Prompt preview", "description": "Writes the future LLM prompt into last_prompt.txt and waits."},
}


def get_agent_driver(mode: str | None) -> AgentDriver:
    if mode == "json_rule":
        return JsonRuleAgentDriver()
    if mode == "llm_json":
        return OpenAICompatibleDriver()
    if mode == "passive":
        return PassiveAgentDriver()
    if mode == "prompt_preview":
        return PromptPreviewDriver()
    return RuleAgentDriver()


def _order_bound_llm_schedule(scheduled: List[Tuple[Organism, Dict]]) -> List[Tuple[Organism, Dict]]:
    def key(item: Tuple[Organism, Dict]) -> Tuple[int, int, str]:
        org, _ = item
        if not org.llm_session_id:
            org.llm_session_id = f"llm_{org.org_id}"
        last_tick = org.last_llm_tick if org.last_llm_tick >= 0 else -1_000_000
        return (last_tick, org.birth_tick, org.llm_session_id)

    return sorted(scheduled, key=key)


def _rule_fallback(world: "ContextGenomeWorld", org: Organism, observation: Dict, reason: str) -> Action:
    from context_genome.engine import rule_agent

    action = rule_agent.decide(world, org, observation)
    action.note = f"{reason}; rule fallback"
    return action


def _consume_llm_result(
    world: "ContextGenomeWorld",
    org: Organism,
    item: LLMBatchItem,
    submitted_tick: int,
) -> Action:
    try:
        result = item.future.result() if item.future is not None else None
    except LLMDriverError as exc:
        world.record_event(
            "llm",
            f"LLM call failed for {org.org_id}",
            actor_id=org.org_id,
            severity="warn",
            data={"error": str(exc)[:500], "model": item.model, "submitted_tick": submitted_tick},
        )
        return item.fallback
    except Exception as exc:
        world.record_event(
            "llm",
            f"LLM call failed for {org.org_id}",
            actor_id=org.org_id,
            severity="warn",
            data={"error": str(exc)[:500], "model": item.model, "submitted_tick": submitted_tick},
        )
        return item.fallback
    if result is None:
        return item.fallback

    raw = result.content
    if not org.llm_session_id:
        org.llm_session_id = f"llm_{org.org_id}"
    org.llm_turns += 1
    org.last_llm_tick = world.tick
    org.llm_model = item.model
    usage = world.record_llm_usage(result.usage)
    _write_virtual_file(
        org,
        "last_llm_response.json",
        json.dumps({"content": raw, "usage": usage}, ensure_ascii=False)[:4096],
    )
    parsed = parse_action_text(org.org_id, raw)
    dialogue_user = item.user_message or item.dialogue_user_message
    sanitized_action: Action | None = None
    if parsed.ok:
        sanitized_action = _sanitize_llm_action(world, org, parsed.action)
        parsed.action = sanitized_action
        dialogue_assistant = json.dumps(
            _action_for_wire(sanitized_action),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    else:
        dialogue_assistant = f"invalid JSON action: {raw[:900]}"
    _append_dialogue_message_pair(org, dialogue_user, dialogue_assistant)
    if item.skill_hash:
        _mark_skill_prompt_seen(org, item.skill_hash)
    world.record_event(
        "llm",
        f"{org.org_id} received LLM action text",
        actor_id=org.org_id,
        data={
            "raw": raw[:1000],
            "ok": parsed.ok,
            "model": item.model,
            "usage": usage,
            "submitted_tick": submitted_tick,
            "latency_ticks": max(0, world.tick - submitted_tick),
        },
    )
    if not parsed.ok:
        _record_parse_failure(world, org, parsed.raw, parsed.error)
        return item.fallback
    parsed.action.note = (parsed.action.note or "llm batch result")[:240]
    return parsed.action


def _sanitize_llm_action(world: "ContextGenomeWorld", org: Organism, action: Action) -> Action:
    bid_caps = {
        "harvest": 2,
        "scan": 1,
        "copy": 4,
        "move": 2,
        "steal": 2,
        "delete": 2,
        "reflect": 2,
        "write": 2,
        "repair": 2,
        "protect": 2,
    }
    cap = bid_caps.get(action.action)
    if cap is not None and action.energy_bid > cap:
        action.energy_bid = cap
        note = action.note or "bid capped"
        action.note = f"{note}; bid capped"[:240]
    if action.action == "copy" and org.energy < 16:
        return Action(
            actor_id=org.org_id,
            action="harvest",
            target_cell=org.cell,
            energy_bid=1,
            note="copy deferred; low energy",
        )
    if action.action == "reflect":
        action.target = world.file_path(org, "SKILL.md")
        action.payload = action.payload[:300]
    if action.action in {"move", "steal", "delete", "reflect", "write", "repair", "protect"}:
        required_energy = world._base_cost(action) + world._maintenance_cost(org) + 1.0
        if org.energy < required_energy:
            return Action(
                actor_id=org.org_id,
                action="harvest",
                target_cell=org.cell,
                energy_bid=1,
                note=f"{action.action} deferred; low energy",
            )
    if action.action == "steal":
        target = world.resolve_org_from_path(action.target or "")
        if target is None or target.org_id == org.org_id:
            return Action(
                actor_id=org.org_id,
                action="scan",
                target_cell=action.target_cell or org.cell,
                energy_bid=0,
                note="invalid steal; scan",
            )
    return action


def _action_for_wire(action: Action) -> dict:
    data = action.as_dict()
    data.pop("actor_id", None)
    return {key: value for key, value in data.items() if value not in (None, "", [])}


def _write_virtual_file(org: Organism, path: str, content: str) -> None:
    file = org.files.get(path)
    if file is None:
        org.files[path] = VFile(path=path, content=content, status="modified")
        return
    file.content = content
    file.status = "modified"
    file.corruption = 0.0


def _file_content(org: Organism, path: str) -> str:
    file = org.files.get(path)
    return file.content if file is not None else ""


def _load_dialogue_messages(org: Organism, limit: int = DIALOGUE_HISTORY_LIMIT) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for line in _file_content(org, "dialogue.jsonl").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
            continue
        content = str(item.get("content") or "")
        if content:
            rows.append({"role": str(item["role"]), "content": content[:DIALOGUE_CONTENT_LIMIT]})
    return rows[-limit:]


def _append_dialogue_message_pair(
    org: Organism,
    user_message: str,
    assistant_message: str,
    limit: int = DIALOGUE_HISTORY_LIMIT,
) -> None:
    rows = _load_dialogue_messages(org, limit=limit - 2)
    rows.extend(
        [
            {"role": "user", "content": user_message[:DIALOGUE_CONTENT_LIMIT]},
            {"role": "assistant", "content": assistant_message[:DIALOGUE_CONTENT_LIMIT]},
        ]
    )
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows[-limit:]) + "\n"
    _write_virtual_file(org, "dialogue.jsonl", content)


def _skill_prompt_policy(org: Organism) -> Dict[str, Any]:
    skill_text = org.skill_text()
    skill_hash = sha1(skill_text.encode("utf-8")).hexdigest()[:16]
    state = _load_prompt_state(org)
    seen_hash = str(state.get("skill_hash") or "")
    seen_turns = int(state.get("turns") or 0)
    unchanged_after_seen = seen_hash == skill_hash and seen_turns > 0
    return {
        "mode": "summary" if unchanged_after_seen else "full",
        "hash": skill_hash,
        "summary": _summarize_skill(skill_text),
    }


def _load_prompt_state(org: Organism) -> Dict[str, Any]:
    text = _file_content(org, PROMPT_STATE_FILE)
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _mark_skill_prompt_seen(org: Organism, skill_hash: str) -> None:
    state = _load_prompt_state(org)
    turns = int(state.get("turns") or 0) + 1
    _write_virtual_file(
        org,
        PROMPT_STATE_FILE,
        json.dumps({"skill_hash": skill_hash, "turns": turns}, ensure_ascii=False),
    )


def _summarize_skill(skill_text: str) -> str:
    try:
        from context_genome.engine import rule_agent

        strategy = rule_agent.infer_strategy(skill_text)
    except Exception:
        strategy = "unknown"
    lines = [line.strip() for line in skill_text.splitlines() if line.strip()]
    keywords = (
        "strategy",
        "ability.",
        "ability_",
        "_efficiency",
        "attack_power",
        "defense_power",
        "local_trait",
        "cell_hint",
        "cell_rule",
        "prefer",
        "avoid",
        "copy",
        "harvest",
        "reflect",
        "repair",
        "protect",
        "move",
        "steal",
        "delete",
        "persist",
        "energy",
    )
    selected: List[str] = []
    for line in lines:
        lower = line.lower()
        if line.startswith("#") and len(selected) < 2:
            selected.append(line)
        elif any(keyword in lower for keyword in keywords):
            selected.append(line)
        if len(selected) >= 10:
            break
    if not selected:
        selected = lines[:12]
    text = "\n".join([f"inferred_strategy: {strategy}", *selected])
    return text[:800]


def _dialogue_observation_summary(
    world: "ContextGenomeWorld",
    org: Organism,
    observation: Dict[str, Any],
    skill_policy: Dict[str, Any],
) -> str:
    self_obs = observation.get("self") if isinstance(observation.get("self"), dict) else {}
    nearby = observation.get("nearby") if isinstance(observation.get("nearby"), list) else []
    nearby_parts = []
    for item in nearby[:8]:
        if not isinstance(item, dict):
            continue
        signals = item.get("signals") if isinstance(item.get("signals"), list) else []
        nearby_parts.append(f"{item.get('cell')}:{'/'.join(str(signal) for signal in signals[:3])}")
    recent = observation.get("recent_events") if isinstance(observation.get("recent_events"), list) else []
    return "\n".join(
        [
            f"World decision context at tick {world.tick} for {org.org_id}.",
            f"skill_mode={skill_policy.get('mode')}, skill_hash={skill_policy.get('hash')}",
            (
                "organism_state="
                f"energy:{self_obs.get('visible_energy')}, "
                f"integrity:{self_obs.get('visible_integrity')}, "
                f"trait:{self_obs.get('local_skill_trait')}, "
                f"capacity:{self_obs.get('local_capacity')}"
            ),
            "nearby=" + "; ".join(nearby_parts[:8]),
            "recent=" + " | ".join(str(item) for item in recent[-3:]),
        ]
    )[:DIALOGUE_CONTENT_LIMIT]


def llm_runtime_status(config_model: str = "") -> dict:
    runtime = _llm_runtime(config_model)
    return {
        "configured": runtime["configured"],
        "missing": runtime["missing"],
        "model": runtime["model"],
        "base_url": runtime["base_url"],
        "json_mode": runtime["json_mode"],
        "disable_thinking": runtime["disable_thinking"],
        "has_api_key": bool(runtime["api_key"]),
    }


def update_llm_runtime_overrides(
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    clear_api_key: bool = False,
    config_model: str = "",
) -> dict:
    with _RUNTIME_OVERRIDE_LOCK:
        if clear_api_key:
            _RUNTIME_OVERRIDES.pop("api_key", None)
        elif api_key is not None and api_key.strip():
            _RUNTIME_OVERRIDES["api_key"] = api_key.strip()
        if base_url is not None:
            clean_base = base_url.strip().rstrip("/")
            if clean_base:
                _RUNTIME_OVERRIDES["base_url"] = clean_base
            else:
                _RUNTIME_OVERRIDES.pop("base_url", None)
    return llm_runtime_status(config_model)


def _runtime_overrides() -> Dict[str, str]:
    with _RUNTIME_OVERRIDE_LOCK:
        return dict(_RUNTIME_OVERRIDES)


def _llm_runtime(config_model: str = "") -> dict:
    overrides = _runtime_overrides()
    api_key = (
        overrides.get("api_key")
        or os.environ.get("CONTEXT_GENOME_LLM_API_KEY")
        or os.environ.get("SKILL_GARDEN_LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    )
    base_url = (
        overrides.get("base_url")
        or os.environ.get("CONTEXT_GENOME_LLM_BASE_URL")
        or os.environ.get("SKILL_GARDEN_LLM_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).rstrip("/")
    model = (
        config_model.strip()
        or os.environ.get("CONTEXT_GENOME_LLM_MODEL", "").strip()
        or os.environ.get("SKILL_GARDEN_LLM_MODEL", "").strip()
        or os.environ.get("OPENAI_MODEL", "").strip()
    )
    json_mode_raw = (
        os.environ.get("CONTEXT_GENOME_LLM_JSON_MODE")
        or os.environ.get("SKILL_GARDEN_LLM_JSON_MODE")
        or "1"
    )
    json_mode = json_mode_raw not in {"0", "false", "False"}
    disable_thinking_raw = os.environ.get("CONTEXT_GENOME_LLM_DISABLE_THINKING")
    if disable_thinking_raw is None:
        disable_thinking_raw = os.environ.get("SKILL_GARDEN_LLM_DISABLE_THINKING")
    disable_thinking = (
        disable_thinking_raw not in {"0", "false", "False"}
        if disable_thinking_raw is not None
        else "deepseek" in base_url.lower()
    )
    missing = []
    if not api_key:
        missing.append("api_key")
    if not model:
        missing.append("model")
    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "json_mode": json_mode,
        "disable_thinking": disable_thinking,
        "configured": not missing,
        "missing": missing,
    }


def _call_chat_completion(
    messages: List[Dict[str, str]],
    runtime: dict,
    temperature: float,
    max_tokens: int,
    timeout_seconds: float,
) -> LLMResult:
    payload = {
        "model": runtime["model"],
        "messages": messages,
        "temperature": max(0.0, min(2.0, temperature)),
        "max_tokens": max(64, min(2048, max_tokens)),
    }
    if runtime["json_mode"]:
        payload["response_format"] = {"type": "json_object"}
    if runtime.get("disable_thinking"):
        payload["thinking"] = {"type": "disabled"}

    raw = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{runtime['base_url']}/chat/completions",
        data=raw,
        headers={
            "Authorization": f"Bearer {runtime['api_key']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=max(1.0, timeout_seconds)) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise LLMDriverError(f"HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LLMDriverError(str(exc)) from exc

    try:
        content = str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMDriverError("chat completion response did not contain choices[0].message.content") from exc
    return LLMResult(content=content, usage=_extract_usage(data, messages, content))


def _extract_usage(data: dict, messages: List[Dict[str, str]], content: str) -> Dict[str, int | bool]:
    usage = data.get("usage") if isinstance(data, dict) else {}
    usage = usage if isinstance(usage, dict) else {}
    prompt_tokens = _int_usage(usage, "prompt_tokens", "input_tokens")
    completion_tokens = _int_usage(usage, "completion_tokens", "output_tokens")
    total_tokens = _int_usage(usage, "total_tokens")
    cache_hit_tokens = _int_usage(usage, "prompt_cache_hit_tokens")
    cache_miss_tokens = _int_usage(usage, "prompt_cache_miss_tokens")
    estimated = False
    if prompt_tokens <= 0 and completion_tokens <= 0 and total_tokens <= 0:
        prompt_tokens = _estimate_token_count(json.dumps(messages, ensure_ascii=False))
        completion_tokens = _estimate_token_count(content)
        total_tokens = prompt_tokens + completion_tokens
        estimated = True
    elif total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "prompt_cache_hit_tokens": cache_hit_tokens,
        "prompt_cache_miss_tokens": cache_miss_tokens,
        "estimated": estimated,
    }


def _int_usage(usage: dict, *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if isinstance(value, (int, float)):
            return max(0, int(value))
    return 0


def _estimate_token_count(text: str) -> int:
    if not text:
        return 0
    return max(1, int(len(text) / 4))


def _record_parse_failure(world: "ContextGenomeWorld", org: Organism, raw: str, error: str) -> None:
    org.parse_failure_count += 1
    org.energy = max(0.0, org.energy - org.parse_failure_count)
    org.integrity = max(0.0, org.integrity - 0.01)
    world.record_event(
        "parse",
        f"{org.org_id} produced invalid JSON action",
        actor_id=org.org_id,
        severity="warn",
        data={"raw": raw[:1000], "error": error},
    )
