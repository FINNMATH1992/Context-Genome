from __future__ import annotations

import argparse
import json
import mimetypes
import threading
from collections import Counter
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from .agents import AGENT_MODES
from .agents.drivers import LLMDriverError, _call_chat_completion, _llm_runtime, llm_runtime_status
from .engine import ContextGenomeWorld, get_preset
from .engine.exporter import list_runs, load_run, save_run
from .engine.presets import PRESET_SEEDS, PRESETS, FORAGER_SKILL


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
RUN_ROOT = ROOT.parent / "runs"


class GenomeState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.world = ContextGenomeWorld(get_preset("sandbox"), seed=7)

    def reset(self, preset: str, seed: int | None, overrides: Dict[str, Any] | None = None) -> dict:
        with self.lock:
            config = get_preset(preset, overrides or {})
            self.world = ContextGenomeWorld(config, seed=seed)
            return self.world.snapshot()


STATE = GenomeState()


class GenomeHandler(BaseHTTPRequestHandler):
    server_version = "ContextGenome/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api_get(parsed.path, parse_qs(parsed.query))
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self._send_json({"error": "not found"}, status=404)
            return
        body = self._read_json()
        self._handle_api_post(parsed.path, body)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle_api_get(self, path: str, query: Dict[str, list]) -> None:
        with STATE.lock:
            world = STATE.world
            if path == "/api/state":
                self._send_json(world.snapshot())
                return
            if path == "/api/presets":
                self._send_json(
                    {
                        "presets": {name: asdict(config) for name, config in PRESETS.items()},
                        "agent_modes": AGENT_MODES,
                        "llm_runtime": llm_runtime_status(world.config.llm_model),
                        "seed_skills": {name: skills for name, skills in PRESET_SEEDS.items()},
                        "default_skill": FORAGER_SKILL,
                    }
                )
                return
            if path == "/api/runs":
                self._send_json({"runs": list_runs(RUN_ROOT)})
                return
            if path == "/api/cell":
                x = int(query.get("x", ["0"])[0])
                y = int(query.get("y", ["0"])[0])
                self._send_json(world.cell_snapshot(x, y))
                return
            if path == "/api/org":
                org_id = query.get("id", [""])[0]
                payload = world.org_snapshot(org_id)
                if payload is None:
                    self._send_json({"error": "organism not found"}, status=404)
                else:
                    self._send_json(payload)
                return
        self._send_json({"error": "not found"}, status=404)

    def _handle_api_post(self, path: str, body: Dict[str, Any]) -> None:
        if path == "/api/report":
            self._handle_report(body)
            return
        with STATE.lock:
            world = STATE.world
            if path == "/api/reset":
                preset = str(body.get("preset") or "sandbox")
                seed = body.get("seed")
                seed = int(seed) if seed not in (None, "") else None
                overrides = body.get("overrides") if isinstance(body.get("overrides"), dict) else {}
                self._send_json(STATE.reset(preset, seed, overrides))
                return
            if path == "/api/tick":
                overrides = body.get("overrides") if isinstance(body.get("overrides"), dict) else {}
                world.update_config(overrides)
                steps = int(body.get("steps") or 1)
                self._send_json(world.step(steps))
                return
            if path == "/api/config":
                overrides = body.get("overrides") if isinstance(body.get("overrides"), dict) else {}
                world.update_config(overrides)
                self._send_json(world.snapshot())
                return
            if path == "/api/spawn":
                x = int(body.get("x", 0))
                y = int(body.get("y", 0))
                skill_text = str(body.get("skill_text") or FORAGER_SKILL)
                label = str(body.get("label") or "Researcher Context")
                energy = float(body.get("energy") or world.config.initial_org_energy)
                org = world.spawn_org(x, y, skill_text, label=label, energy=energy)
                self._send_json({"ok": True, "organism": world.org_snapshot(org.org_id), "state": world.snapshot()})
                return
            if path == "/api/edit_skill":
                org_id = str(body.get("org_id") or "")
                skill_text = str(body.get("skill_text") or "")
                ok = world.edit_skill(org_id, skill_text)
                self._send_json({"ok": ok, "organism": world.org_snapshot(org_id), "state": world.snapshot()})
                return
            if path == "/api/delete_org":
                org_id = str(body.get("org_id") or "")
                ok = world.researcher_delete_org(org_id)
                self._send_json({"ok": ok, "state": world.snapshot()})
                return
            if path == "/api/export":
                summary = save_run(world, RUN_ROOT)
                self._send_json({"ok": True, "summary": summary, "runs": list_runs(RUN_ROOT)})
                return
            if path == "/api/load_run":
                run_id = str(body.get("run_id") or "")
                if not run_id:
                    self._send_json({"error": "run_id required"}, status=400)
                    return
                try:
                    STATE.world = load_run(RUN_ROOT, run_id)
                except FileNotFoundError:
                    self._send_json({"error": "run not found"}, status=404)
                    return
                self._send_json({"ok": True, "state": STATE.world.snapshot()})
                return
        self._send_json({"error": "not found"}, status=404)

    def _handle_report(self, body: Dict[str, Any]) -> None:
        with STATE.lock:
            world = STATE.world
            overrides = body.get("overrides") if isinstance(body.get("overrides"), dict) else {}
            world.update_config(overrides)
            report_context = _build_report_context(world)
            runtime = _llm_runtime(world.config.llm_model)
            timeout_seconds = float(world.config.llm_timeout_seconds)
            temperature = min(0.5, max(0.0, float(world.config.llm_temperature)))

        if not runtime["configured"]:
            self._send_json({"ok": False, "error": "llm not configured", "missing": runtime["missing"]}, status=400)
            return
        report_runtime = dict(runtime)
        report_runtime["json_mode"] = False
        messages = _build_report_messages(report_context)
        try:
            result = _call_chat_completion(
                messages,
                report_runtime,
                temperature,
                1400,
                timeout_seconds,
            )
        except LLMDriverError as exc:
            self._send_json({"ok": False, "error": str(exc)[:1000]}, status=502)
            return
        with STATE.lock:
            usage = STATE.world.record_llm_usage(result.usage)
            STATE.world.record_event(
                "report",
                "researcher generated bilingual ecology report",
                data={"usage": usage},
            )
            state = STATE.world.snapshot()
        self._send_json({"ok": True, "report": result.content, "usage": usage, "context": report_context, "state": state})

    def _serve_static(self, request_path: str) -> None:
        if request_path in {"", "/"}:
            path = WEB_ROOT / "index.html"
        else:
            safe_name = request_path.lstrip("/")
            path = WEB_ROOT / safe_name
        if not path.exists() or not path.is_file() or WEB_ROOT not in path.resolve().parents and path.resolve() != WEB_ROOT:
            self._send_json({"error": "not found"}, status=404)
            return
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Context Genome browser observer.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    args = parser.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), GenomeHandler)
    print(f"Context Genome running at http://{args.host}:{args.port}")
    httpd.serve_forever()


def _build_report_context(world: ContextGenomeWorld) -> Dict[str, Any]:
    stats = world.stats()
    lineages = world.lineage_snapshot(limit=8)
    top_lineage = lineages[0] if lineages else None
    live_orgs = [org for org in world.orgs.values() if org.alive]
    action_counts = Counter(event.kind for event in world.events[-120:])
    occupied_cells = sum(1 for cell in world.cells.values() if any(world.orgs.get(oid) and world.orgs[oid].alive for oid in cell.org_ids))
    corpse_cells = sum(1 for cell in world.cells.values() if any(world.orgs.get(oid) and not world.orgs[oid].alive for oid in cell.org_ids))
    cell_count = max(1, len(world.cells))
    top_resource_cells = sorted(world.cells.values(), key=lambda cell: cell.energy, reverse=True)[:6]
    risky_cells = sorted(world.cells.values(), key=lambda cell: (cell.radiation + cell.local_entropy), reverse=True)[:6]
    representative = None
    if top_lineage:
        candidates = [org for org in live_orgs if org.lineage_id == top_lineage["lineage_id"]]
        if candidates:
            representative = max(candidates, key=lambda org: (org.energy + org.integrity * 40 + org.generation * 2 + org.llm_turns))
    strongest_orgs = sorted(
        live_orgs,
        key=lambda org: (org.energy + org.integrity * 35 + org.generation * 2 + org.llm_turns),
        reverse=True,
    )[:8]
    cache_hit = int(stats.get("llm_prompt_cache_hit_tokens") or 0)
    cache_miss = int(stats.get("llm_prompt_cache_miss_tokens") or 0)
    cache_total = cache_hit + cache_miss
    return {
        "product": "Context Genome",
        "task": (
            "Generate a bilingual ecology report. Output English first, then Chinese. "
            "Identify the strongest lineage, explain why it is leading, and summarize its representative context genome/SKILL.md."
        ),
        "tick": world.tick,
        "config": {
            "preset": world.config.name,
            "ecology_label": world.config.ecology_label,
            "agent_mode": world.config.agent_mode,
            "allow_conflict": world.config.allow_conflict,
            "allow_delete": world.config.allow_delete,
            "enable_mutation": world.config.enable_mutation,
            "enable_disasters": world.config.enable_disasters,
            "world": [world.config.world_width, world.config.world_height],
        },
        "stats": stats,
        "derived_metrics": {
            "occupied_cells": occupied_cells,
            "corpse_cells": corpse_cells,
            "avg_cell_energy": stats.get("total_cell_energy", 0) / cell_count,
            "recent_action_counts": dict(action_counts.most_common(12)),
            "llm_cache_hit_rate": cache_hit / cache_total if cache_total else 0,
        },
        "lineages": lineages,
        "strongest_lineage": top_lineage,
        "strongest_lineage_representative": _report_org(world, representative, include_skill=True) if representative else None,
        "strongest_organisms": [_report_org(world, org, include_skill=False) for org in strongest_orgs],
        "top_resource_cells": [_report_cell(cell) for cell in top_resource_cells],
        "risky_cells": [_report_cell(cell) for cell in risky_cells],
        "recent_events": [event.as_dict() for event in world.events[-36:]],
        "history_tail": world.history[-16:],
    }


def _report_org(world: ContextGenomeWorld, org, include_skill: bool = False) -> Dict[str, Any]:
    data = {
        "org_id": org.org_id,
        "lineage_id": org.lineage_id,
        "cell": org.cell,
        "generation": org.generation,
        "energy": round(org.energy, 2),
        "integrity": round(org.integrity, 3),
        "age": org.age,
        "tags": org.tags,
        "strategy": world._org_summary(org, include_skill=False)["strategy"],
        "abilities": world._org_summary(org, include_skill=False)["abilities"],
        "llm_turns": org.llm_turns,
    }
    if include_skill:
        data["context_genome_skill"] = org.skill_text()[:4000]
    else:
        data["context_preview"] = org.skill_text()[:500]
    return data


def _report_cell(cell) -> Dict[str, Any]:
    return {
        "cell": [cell.x, cell.y],
        "energy": round(cell.energy, 2),
        "mineral": round(cell.mineral, 2),
        "radiation": round(cell.radiation, 4),
        "entropy": round(cell.local_entropy, 4),
        "trait": cell.skill_trait,
        "organisms": len(cell.org_ids),
    }


def _build_report_messages(report_context: Dict[str, Any]) -> list[dict[str, str]]:
    system = "\n".join(
        [
            "You are a research analyst for Context Genome, an LLM context evolution sandbox.",
            "Interpret the project as context-layer evolution: the base LLM is a mostly homogeneous understanding substrate, while context genomes impose personality, goals, methods, and behavioral constraints.",
            "When analyzing winners, focus on which context constraints are being selected by the environment, not on model-weight learning.",
            "Use only the provided JSON context. Do not invent hidden state.",
            "Write a concise Markdown report.",
            "The report must contain English first, then Chinese.",
            "In both languages cover: current ecology status, strongest lineage, representative context genome/SKILL.md, behavior trends, risks, LLM/cache status, and suggested next experiments.",
            "When describing the strongest lineage's skill, cite concrete strategy and ability lines from context_genome_skill.",
        ]
    )
    user = "\n".join(
        [
            "Current global world state JSON:",
            json.dumps(report_context, ensure_ascii=False, separators=(",", ":")),
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


if __name__ == "__main__":
    main()
