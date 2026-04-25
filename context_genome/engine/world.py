from __future__ import annotations

import json
import math
import random
import string
from collections import Counter, defaultdict
from dataclasses import asdict
from typing import Dict, Iterable, List, Optional, Tuple

from context_genome.agents import get_agent_driver

from . import rule_agent
from .models import Action, Cell, Coord, Event, GardenConfig, Organism, VFile
from .presets import PRESET_SEEDS


HEX = string.hexdigits.lower()[:16]


class ContextGenomeWorld:
    def __init__(
        self,
        config: GardenConfig,
        seed: Optional[int] = None,
        initial_skills: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        self.config = config
        self.rng = random.Random(seed)
        self.seed = seed
        self.agent_driver = get_agent_driver(config.agent_mode)
        self.llm_calls_this_tick = 0
        self.decision_batch = None
        self.tick = 0
        self.cells: Dict[Coord, Cell] = {}
        self.orgs: Dict[str, Organism] = {}
        self.events: List[Event] = []
        self.history: List[dict] = []
        self.lineage_history: List[dict] = []
        self.llm_usage = self._empty_llm_usage()
        self.llm_budget_exhausted_reported = False
        self.birth_count = 0
        self.death_count = 0
        self.lineage_births: Dict[str, int] = defaultdict(int)
        self.lineage_first_seen: Dict[str, int] = {}
        self._build_cells()
        self._seed_initial_population(initial_skills)
        self._snapshot_history()

    def _build_cells(self) -> None:
        for y in range(self.config.world_height):
            for x in range(self.config.world_width):
                energy = self.config.initial_cell_energy * self.rng.uniform(0.78, 1.25)
                mineral = self.config.initial_cell_mineral * self.rng.uniform(0.75, 1.2)
                radiation = self.config.radiation_default * self.rng.uniform(0.5, 1.6)
                entropy = self.rng.uniform(0.04, 0.18)
                skill_trait, skill_fragment = self._make_cell_skill(x, y, energy, mineral, radiation, entropy)
                self.cells[(x, y)] = Cell(
                    x=x,
                    y=y,
                    energy=energy,
                    mineral=mineral,
                    radiation=radiation,
                    capacity=self.config.cell_capacity,
                    local_entropy=entropy,
                    skill_trait=skill_trait,
                    skill_fragment=skill_fragment,
                )

    def _make_cell_skill(
        self,
        x: int,
        y: int,
        energy: float,
        mineral: float,
        radiation: float,
        entropy: float,
    ) -> Tuple[str, str]:
        traits = [
            ("forage", "prefer harvest when local energy is above neighbor pressure"),
            ("spread", "prefer compact copies into lower-crowding cells"),
            ("guard", "protect SKILL.md after nearby write activity"),
            ("repair", "repair when integrity falls before copying"),
            ("migrate", "move away from depleted or crowded cells"),
            ("minimal", "keep directory small before long-distance copying"),
            ("scavenge", "read residues and reuse stable fragments"),
            ("steal", "sample useful lines from nearby foreign SKILL.md files"),
        ]
        trait, hint = traits[(x * 7 + y * 11 + int(energy + mineral)) % len(traits)]
        marker = f"# Local Cell Skill {x:02d}_{y:02d}"
        fragment = "\n".join(
            [
                marker,
                f"local_trait: {trait}_{x:02d}_{y:02d}",
                f"cell_hint: {hint}.",
                f"cell_risk: radiation {radiation:.3f}, entropy {entropy:.3f}.",
                "cell_rule: append only if this fragment improves persistence.",
            ]
        )
        return trait, fragment + "\n"

    def _seed_initial_population(self, initial_skills: Optional[List[Tuple[str, str]]]) -> None:
        skills = initial_skills or PRESET_SEEDS.get(self.config.name, PRESET_SEEDS["sandbox"])
        for index in range(self.config.initial_orgs):
            label, skill = skills[index % len(skills)]
            coord = self._random_sparse_cell()
            org = self.spawn_org(
                coord[0],
                coord[1],
                skill,
                label=label,
                energy=self.config.initial_org_energy * self.rng.uniform(0.8, 1.25),
                record=False,
            )
            self.record_event(
                "birth",
                f"{org.org_id} seeded as {label}",
                actor_id=org.org_id,
                target=self.org_path(org),
                data={"lineage_id": org.lineage_id, "label": label},
            )

    def _random_sparse_cell(self) -> Coord:
        choices = list(self.cells.values())
        self.rng.shuffle(choices)
        choices.sort(key=lambda cell: (len(cell.org_ids), -cell.energy))
        return choices[0].coord()

    def spawn_org(
        self,
        x: int,
        y: int,
        skill_text: str,
        label: str = "Seed",
        energy: Optional[float] = None,
        lineage_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        generation: int = 0,
        files: Optional[Dict[str, VFile]] = None,
        org_id: Optional[str] = None,
        integrity: float = 1.0,
        tags: Optional[List[str]] = None,
        record: bool = True,
    ) -> Organism:
        coord = self._clamp_coord((x, y))
        cell = self.cell_at(coord)
        org_id = self._unique_id("org", org_id)
        if lineage_id is None:
            lineage_id = self._unique_id("lin")
            self.lineage_first_seen[lineage_id] = self.tick
        if files is None:
            skill_text = self._skill_with_cell_fragment(skill_text, cell)
            files = {
                "SKILL.md": VFile("SKILL.md", skill_text),
                "memory.md": VFile("memory.md", f"Seeded as {label} at tick {self.tick}.\n"),
                "genome.json": VFile(
                    "genome.json",
                    json.dumps({"label": label, "strategy": rule_agent.infer_strategy(skill_text)}),
                ),
            }
        tags = self._org_tags(
            label=label,
            org_id=org_id,
            skill_text=skill_text,
            lineage_id=lineage_id,
            generation=generation,
            parent_id=parent_id,
            base_tags=tags,
            status="alive",
        )
        org = Organism(
            org_id=org_id,
            lineage_id=lineage_id,
            parent_id=parent_id,
            generation=generation,
            cell=coord,
            energy=energy if energy is not None else self.config.initial_org_energy,
            integrity=max(0.05, min(1.0, integrity)),
            files=files,
            tags=tags,
            mutation_rate=self.config.base_mutation_rate,
            birth_tick=self.tick,
            llm_session_id=f"llm_{org_id}",
        )
        self.orgs[org_id] = org
        cell.org_ids.append(org_id)
        self.birth_count += 1
        self.lineage_births[lineage_id] += 1
        self.lineage_first_seen.setdefault(lineage_id, self.tick)
        if record:
            self.record_event(
                "birth",
                f"{org_id} became runnable in cell {coord[0]:02d}_{coord[1]:02d}",
                actor_id=org_id,
                target=self.org_path(org),
                data={"lineage_id": lineage_id, "parent_id": parent_id},
            )
        return org

    def _org_tags(
        self,
        label: str,
        org_id: str,
        skill_text: str,
        lineage_id: str,
        generation: int,
        parent_id: Optional[str] = None,
        base_tags: Optional[List[str]] = None,
        status: str = "alive",
    ) -> List[str]:
        strategy = rule_agent.infer_strategy(skill_text)
        label_slug = self._tag_slug(label or strategy, "seed")
        unit_slug = self._tag_slug(f"{label_slug}-{org_id[-4:]}", org_id[-6:])
        tags = self._normalize_tags(base_tags or [])
        dynamic_prefixes = ("status:", "lineage:", "gen:", "parent:", "unit:", "skill:")
        tags = [tag for tag in tags if not tag.startswith(dynamic_prefixes)]
        if not any(tag.startswith("seed:") for tag in tags):
            tags.append(f"seed:{label_slug}")
        if not any(tag.startswith("origin:") for tag in tags):
            tags.append(f"origin:{self._tag_slug(strategy, 'unknown')}")
        for declared in self._skill_declared_tags(skill_text):
            if declared not in tags:
                tags.append(declared)
        tags.extend(
            [
                f"unit:{unit_slug}",
                f"lineage:{lineage_id[-6:]}",
                f"gen:{generation}",
            ]
        )
        if parent_id:
            tags.append(f"parent:{parent_id[-6:]}")
        return self._set_status_tag(tags, status)

    def _skill_declared_tags(self, skill_text: str) -> List[str]:
        tags: List[str] = []
        for line in skill_text.splitlines():
            if ":" not in line:
                continue
            key, raw = line.split(":", 1)
            if key.strip().lower() not in {"tag", "tags"}:
                continue
            for item in raw.replace(";", ",").split(","):
                slug = self._tag_slug(item.strip(), "")
                if slug:
                    tags.append(f"skill:{slug}")
        return tags[:6]

    def _tag_slug(self, value: str, fallback: str) -> str:
        text = str(value or "").strip().lower()
        chars = []
        previous_dash = False
        for char in text:
            if char.isalnum():
                chars.append(char)
                previous_dash = False
            elif not previous_dash:
                chars.append("-")
                previous_dash = True
        slug = "".join(chars).strip("-")[:32]
        return slug or fallback

    def _normalize_tags(self, tags: List[str]) -> List[str]:
        normalized: List[str] = []
        aliases = {
            "viable": "status:alive",
            "alive": "status:alive",
            "corpse": "status:corpse",
            "revived": "status:revived",
            "removed": "status:removed",
        }
        for raw in tags:
            text = str(raw or "").strip().lower()
            if not text:
                continue
            text = aliases.get(text, text)
            if ":" in text:
                prefix, value = text.split(":", 1)
                prefix = self._tag_slug(prefix, "tag")
                value = self._tag_slug(value, "")
                if not value:
                    continue
                tag = f"{prefix}:{value}"
            else:
                tag = self._tag_slug(text, "")
            if tag and tag not in normalized:
                normalized.append(tag)
        return normalized[:16]

    def _set_status_tag(self, tags: List[str], status: str) -> List[str]:
        status_tag = f"status:{self._tag_slug(status, 'alive')}"
        normalized = [tag for tag in self._normalize_tags(tags) if not tag.startswith("status:")]
        return [status_tag, *normalized][:16]

    def step(self, steps: int = 1) -> dict:
        steps = max(1, min(steps, 200))
        for _ in range(steps):
            if self._llm_token_budget_exhausted() and getattr(self, "decision_batch", None) is None:
                self._record_llm_budget_pause()
                break
            self._step_once()
            if self._llm_token_budget_exhausted() and getattr(self, "decision_batch", None) is None:
                self._record_llm_budget_pause()
                break
        return self.snapshot()

    def _step_once(self) -> None:
        batch = getattr(self, "decision_batch", None)
        if batch is not None:
            batch_ready = getattr(self.agent_driver, "batch_ready", None)
            finish_batch = getattr(self.agent_driver, "finish_batch", None)
            if callable(batch_ready) and callable(finish_batch) and not batch_ready(batch):
                return
            self.decision_batch = None
            actions = finish_batch(self, batch) if callable(finish_batch) else []
            self._complete_step(actions)
            return

        self.tick += 1
        self.llm_calls_this_tick = 0
        self._regen_cells()
        viable = self.scan_viable_orgs()
        scheduled = self._schedule(viable)
        scheduled_observations = [(org, self.build_observation(org)) for org in scheduled]
        if not scheduled_observations:
            self._complete_step([])
            return
        start_batch = getattr(self.agent_driver, "start_batch", None)
        batch_ready = getattr(self.agent_driver, "batch_ready", None)
        finish_batch = getattr(self.agent_driver, "finish_batch", None)
        if callable(start_batch) and callable(batch_ready) and callable(finish_batch):
            batch = start_batch(self, scheduled_observations)
            if not batch_ready(batch):
                self.decision_batch = batch
                return
            actions = finish_batch(self, batch)
        else:
            actions = [
                self.agent_driver.decide(self, org, observation)
                for org, observation in scheduled_observations
            ]

        self._complete_step(actions)

    def _complete_step(self, actions: List[Action]) -> None:
        for action in actions:
            org = self.orgs.get(action.actor_id)
            if org:
                org.last_executed_tick = self.tick
            self.record_event(
                "action",
                f"{action.actor_id} proposed {action.action}",
                actor_id=action.actor_id,
                target=action.target or self._format_coord(action.target_cell),
                data={"action": action.as_dict()},
            )

        result_start = len(self.events)
        for group in self._group_actions(actions).values():
            self._resolve_action_group(group)

        self._apply_maintenance()
        self._apply_decay()
        if self.config.enable_disasters:
            self._maybe_apply_disaster()
        self._decay_shields()
        self._append_world_feedback(actions, result_start)
        self._snapshot_history()

    def _append_world_feedback(self, actions: List[Action], result_start: int) -> None:
        if self.config.agent_mode != "llm_json" or not actions:
            return
        messages_by_actor: Dict[str, List[str]] = defaultdict(list)
        for event in self.events[result_start:]:
            if event.actor_id:
                messages_by_actor[event.actor_id].append(event.message)
        for action in actions:
            org = self.orgs.get(action.actor_id)
            if org is None or "dialogue.jsonl" not in org.files:
                continue
            messages = messages_by_actor.get(action.actor_id) or ["no visible result"]
            summary = "; ".join(messages[:5])
            status = f"post_energy={org.energy:.1f}, integrity={org.integrity:.2f}, alive={org.alive}"
            content = f"World result tick {self.tick}: action {action.action}. {summary}. {status}"
            self._append_dialogue_line(org, "user", content)

    def _append_dialogue_line(self, org: Organism, role: str, content: str, limit: int = 8) -> None:
        rows: List[Dict[str, str]] = []
        existing = org.files.get("dialogue.jsonl")
        for line in (existing.content if existing else "").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict) or item.get("role") not in {"user", "assistant"}:
                continue
            item_content = str(item.get("content") or "")
            if item_content:
                rows.append({"role": str(item["role"]), "content": item_content[:1200]})
        rows.append({"role": role, "content": content[:1200]})
        org.files["dialogue.jsonl"] = VFile(
            "dialogue.jsonl",
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows[-limit:]) + "\n",
            status="modified",
        )

    def scan_viable_orgs(self) -> List[Organism]:
        viable = []
        for org in self.orgs.values():
            cell = self.cell_at(org.cell)
            if org.is_viable(cell, self.config.max_org_directory_size):
                viable.append(org)
        return viable

    def _schedule(self, viable: Iterable[Organism]) -> List[Organism]:
        by_cell: Dict[Coord, List[Tuple[float, Organism]]] = defaultdict(list)
        for org in viable:
            cell = self.cell_at(org.cell)
            relatives = sum(
                1
                for oid in cell.org_ids
                if oid in self.orgs
                and self.orgs[oid].alive
                and self.orgs[oid].lineage_id == org.lineage_id
            )
            freshness_penalty = 1 / math.sqrt(1 + relatives)
            adaptation = max(0.25, min(1.5, cell.energy / max(1, self.config.initial_cell_energy)))
            score = (
                org.energy
                * org.integrity
                * adaptation
                * freshness_penalty
                * self.rng.uniform(0.8, 1.2)
            )
            by_cell[org.cell].append((score, org))

        selected: List[Organism] = []
        for scored in by_cell.values():
            scored.sort(key=lambda item: item[0], reverse=True)
            selected.extend(org for _, org in scored[: self.config.max_active_per_cell])
        self.rng.shuffle(selected)
        return selected[: self.config.max_total_active_per_tick]

    def build_observation(self, org: Organism) -> dict:
        cell = self.cell_at(org.cell)
        nearby = []
        for neighbor in self.neighbor_cells(org.cell, include_self=False):
            signals = []
            live_count = sum(1 for oid in neighbor.org_ids if self.orgs.get(oid) and self.orgs[oid].alive)
            if live_count:
                signals.append("many_files" if live_count > 2 else "some_files")
            else:
                signals.append("empty_space")
            if neighbor.energy > self.config.initial_cell_energy:
                signals.append("high_energy")
            if neighbor.local_entropy > 0.22:
                signals.append("unstable")
            signals.append(f"local_trait:{neighbor.skill_trait}")
            nearby.append({"cell": neighbor.coord(), "signals": signals})
        recent = [
            event.message
            for event in self.events[-24:]
            if event.actor_id == org.org_id or event.target == self.org_path(org)
        ][-4:]
        return {
                "self": {
                    "path": self.org_path(org),
                    "llm_session": org.llm_session_id or f"llm_{org.org_id}",
                    "llm_turns": org.llm_turns,
                    "last_llm_tick": org.last_llm_tick,
                    "tags": org.tags,
                    "visible_energy": self._bucket(org.energy, [15, 35, 70]),
                    "visible_integrity": self._bucket(org.integrity, [0.45, 0.75, 0.92]),
                    "local_skill_trait": cell.skill_trait,
                "local_capacity": self._bucket(
                    self.cell_directory_size(org.cell) / max(1, cell.capacity),
                    [0.25, 0.6, 0.85],
                ),
            },
            "nearby": nearby,
            "recent_events": recent,
            "allowed_actions": [
                "read",
                "reflect",
                "write",
                "copy",
                "move",
                "steal",
                "delete" if self.config.allow_delete else "scan",
                "scan",
                "harvest",
                "repair",
                "protect",
                "wait",
            ],
        }

    def _group_actions(self, actions: List[Action]) -> Dict[str, List[Action]]:
        grouped: Dict[str, List[Action]] = defaultdict(list)
        for action in actions:
            grouped[self._action_target_key(action)].append(action)
        return grouped

    def _action_target_key(self, action: Action) -> str:
        if action.action in {"harvest", "scan"}:
            return f"cell:{self._format_coord(action.target_cell)}:{action.action}"
        if action.action == "wait":
            return f"wait:{action.actor_id}"
        return f"path:{action.target or action.source or action.actor_id}"

    def _resolve_action_group(self, actions: List[Action]) -> None:
        if not actions:
            return
        if len(actions) == 1 or not self.config.allow_conflict:
            for action in actions:
                self._execute_single(action)
            return
        if all(action.action == "harvest" for action in actions):
            self._resolve_harvest_group(actions)
            return

        scored = [(self._compute_force(action), action) for action in actions]
        scored.sort(key=lambda item: item[0], reverse=True)
        best_force, best = scored[0]
        second_force = scored[1][0] if len(scored) > 1 else 0.001
        ratio = best_force / max(second_force, 0.001)

        if ratio >= 1.25:
            self._execute_single(best, force=best_force)
            for force, action in scored[1:]:
                self._spend(self.orgs[action.actor_id], self._base_cost(action) * 0.45)
                self._damage_actor(action.actor_id, 0.015 if ratio >= 2.0 else 0.035)
                self.record_event(
                    "conflict",
                    f"{action.actor_id} lost conflict on {best.target or best.source}",
                    actor_id=action.actor_id,
                    target=best.target,
                    severity="warn",
                    data={"force": force, "winner": best.actor_id, "winner_force": best_force},
                )
        else:
            target = best.target or best.source
            for force, action in scored:
                org = self.orgs.get(action.actor_id)
                if org:
                    self._spend(org, self._base_cost(action) * 0.65)
                    self._damage_actor(action.actor_id, 0.025)
            if target:
                self._damage_target_path(target, 0.08)
            self.record_event(
                "conflict",
                f"conflict stalemated around {target}",
                target=target,
                severity="warn",
                data={"actors": [action.actor_id for _, action in scored]},
            )

    def _resolve_harvest_group(self, actions: List[Action]) -> None:
        coord = actions[0].target_cell
        if coord is None:
            return
        cell = self.cell_at(coord)
        forces = [(max(0.1, self._compute_force(action)), action) for action in actions]
        total_force = sum(force for force, _ in forces)
        total_requested = sum(4 + action.energy_bid * 2 for _, action in forces)
        harvestable = min(cell.energy, total_requested)
        for force, action in forces:
            share = harvestable * force / max(total_force, 0.001)
            org = self.orgs.get(action.actor_id)
            if not org:
                continue
            ratio = self._spend(org, self._base_cost(action))
            gained = share * ratio
            org.energy += gained
            self.record_event(
                "harvest",
                f"{org.org_id} harvested {gained:.1f} shared energy",
                actor_id=org.org_id,
                target=self._format_coord(coord),
                data={"gained": gained},
            )
        cell.energy = max(0.0, cell.energy - harvestable)
        if harvestable > self.config.energy_regen_per_tick * 2:
            cell.local_entropy = min(1.0, cell.local_entropy + 0.01 * len(actions))

    def _execute_single(self, action: Action, force: Optional[float] = None) -> None:
        org = self.orgs.get(action.actor_id)
        if org is None or not org.alive:
            return
        name = action.action
        if name == "wait":
            self._spend(org, self._base_cost(action))
            org.integrity = min(1.0, org.integrity + 0.004)
            return
        if name == "scan":
            self._spend(org, self._base_cost(action))
            self.record_event(
                "scan",
                f"{org.org_id} scanned {self._format_coord(action.target_cell)}",
                actor_id=org.org_id,
                target=self._format_coord(action.target_cell),
            )
            return
        if name == "read":
            self._spend(org, self._base_cost(action))
            self.record_event("read", f"{org.org_id} read a virtual path", actor_id=org.org_id, target=action.target)
            return
        if name == "reflect":
            self._execute_reflect(action)
            return
        if name == "harvest":
            self._execute_harvest(action)
            return
        if name == "copy":
            self._execute_copy(action)
            return
        if name == "move":
            self._execute_move(action)
            return
        if name == "steal":
            self._execute_steal(action)
            return
        if name == "delete":
            self._execute_delete(action, force=force)
            return
        if name == "write":
            self._execute_write(action)
            return
        if name == "repair":
            self._execute_repair(action)
            return
        if name == "protect":
            self._execute_protect(action)
            return
        self._spend(org, 0.5)

    def _execute_harvest(self, action: Action) -> None:
        org = self.orgs[action.actor_id]
        coord = action.target_cell or org.cell
        cell = self.cell_at(coord)
        if self.distance(org.cell, coord) > 1:
            self._spend(org, 1.0)
            return
        ratio = self._spend(org, self._base_cost(action))
        amount = min(cell.energy, (4 + action.energy_bid * 2) * ratio * self._ability(org, "harvest"))
        cell.energy = max(0.0, cell.energy - amount)
        org.energy += amount
        if amount > self.config.energy_regen_per_tick * 1.7:
            cell.local_entropy = min(1.0, cell.local_entropy + 0.012)
        self.record_event(
            "harvest",
            f"{org.org_id} harvested {amount:.1f} energy",
            actor_id=org.org_id,
            target=self._format_coord(coord),
            data={"gained": amount},
        )

    def _execute_copy(self, action: Action) -> None:
        org = self.orgs[action.actor_id]
        if not action.target:
            return
        parsed = self.parse_path(action.target)
        if parsed is None:
            self._damage_actor(org.org_id, 0.02)
            return
        target_coord, requested_id, _ = parsed
        if self.distance(org.cell, target_coord) > 1:
            self._spend(org, 1.5)
            self._damage_actor(org.org_id, 0.02)
            return
        target_cell = self.cell_at(target_coord)
        copy_efficiency = self._ability(org, "copy")
        source_size = max(1, org.directory_size)
        child_energy = max(6.0, min(14.0, 4.0 + action.energy_bid * 0.75))
        total_cost = self._base_cost(action) + child_energy + source_size / (4096 * copy_efficiency)
        required_energy = total_cost + self._maintenance_cost(org) * 0.5 + 0.5
        if org.energy < required_energy:
            available = org.energy
            self._spend(org, min(available, max(1.0, self._base_cost(action) * 0.35)))
            self.record_event(
                "copy",
                f"{org.org_id} deferred copy because energy was too low",
                actor_id=org.org_id,
                target=action.target,
                severity="warn",
                data={"available": available, "required": required_energy},
            )
            return
        ratio = self._spend(org, total_cost)
        if ratio < 0.35 or self.cell_directory_size(target_coord) + source_size > target_cell.capacity:
            self.record_event(
                "copy",
                f"{org.org_id} left an unrunnable copy trace",
                actor_id=org.org_id,
                target=action.target,
                severity="warn",
                data={"ratio": ratio},
            )
            self._damage_actor(org.org_id, 0.02)
            return
        files = org.clone_files()
        if ratio < 0.72:
            for name in list(files):
                if name != "SKILL.md" and self.rng.random() < 0.5:
                    files.pop(name, None)
        files["SKILL.md"].content = self._skill_with_cell_fragment(files["SKILL.md"].content, target_cell)
        mutation_damage = self._mutate_files(files, org, target_cell) if self.config.enable_mutation else 0.0
        child = self.spawn_org(
            target_coord[0],
            target_coord[1],
            files["SKILL.md"].content,
            label=rule_agent.infer_strategy(files["SKILL.md"].content),
            energy=child_energy * ratio,
            lineage_id=org.lineage_id,
            parent_id=org.org_id,
            generation=org.generation + 1,
            files=files,
            org_id=requested_id,
            integrity=max(0.05, org.integrity * (0.64 + 0.36 * ratio) - mutation_damage),
        )
        self.record_event(
            "copy",
            f"{org.org_id} copied a runnable directory to {child.org_id}",
            actor_id=org.org_id,
            target=self.org_path(child),
            data={"child_id": child.org_id, "lineage_id": child.lineage_id, "ratio": ratio},
        )

    def _execute_move(self, action: Action) -> None:
        org = self.orgs[action.actor_id]
        if not action.target:
            return
        parsed = self.parse_path(action.target)
        if parsed is None:
            self._damage_actor(org.org_id, 0.01)
            return
        target_coord, _, _ = parsed
        if self.distance(org.cell, target_coord) > 1:
            self._spend(org, 1.0)
            return
        if self.cell_directory_size(target_coord) + org.directory_size > self.cell_at(target_coord).capacity:
            self._spend(org, 1.0)
            return
        ratio = self._spend(org, self._base_cost(action))
        if ratio < 0.35:
            self._damage_actor(org.org_id, 0.025)
            return
        old_coord = org.cell
        self._move_org_to_cell(org, target_coord)
        self.record_event(
            "move",
            f"{org.org_id} migrated from {self._format_coord(old_coord)} to {self._format_coord(target_coord)}",
            actor_id=org.org_id,
            target=self.org_path(org),
            data={"ratio": ratio},
        )

    def _execute_steal(self, action: Action) -> None:
        org = self.orgs[action.actor_id]
        target = self.resolve_org_from_path(action.target or "")
        if target is None or target.org_id == org.org_id:
            self._spend(org, 1.0)
            return
        if self.distance(org.cell, target.cell) > 1:
            self._spend(org, 1.0)
            return

        ratio = self._spend(org, self._base_cost(action))
        force = self._compute_force(action)
        if target.shield > force * 1.15:
            target.shield = max(0.0, target.shield - force * 0.25)
            self._damage_actor(org.org_id, 0.015)
            self.record_event(
                "steal",
                f"{org.org_id} failed to sample protected skill from {target.org_id}",
                actor_id=org.org_id,
                target=self.file_path(target, "SKILL.md"),
                severity="warn",
                data={"source_id": target.org_id, "ratio": ratio},
            )
            return
        if ratio < 0.35:
            self._damage_actor(org.org_id, 0.02)
            return

        fragment = self._extract_skill_fragment(target)
        if not fragment:
            return
        if self.config.enable_mutation and self.rng.random() < target.mutation_rate + self.cell_at(org.cell).radiation:
            fragment = self._mutate_fragment(fragment)
        block = "\n".join(
            [
                "",
                f"# Stolen Skill Fragment tick {self.tick}",
                f"stolen_from: {target.org_id}",
                fragment.strip(),
                "",
            ]
        )
        skill = org.files.get("SKILL.md")
        if skill is None:
            return
        new_text = skill.content.rstrip() + "\n" + block
        if len(new_text.encode("utf-8")) > self.config.max_skill_size:
            self.record_event(
                "steal",
                f"{org.org_id} sampled {target.org_id}, but SKILL.md was too large to graft",
                actor_id=org.org_id,
                target=self.file_path(target, "SKILL.md"),
                severity="warn",
                data={"source_id": target.org_id},
            )
            return
        skill.content = new_text
        skill.status = "modified"
        org.integrity = max(0.05, org.integrity - 0.004)
        self.record_event(
            "steal",
            f"{org.org_id} grafted a skill fragment from {target.org_id}",
            actor_id=org.org_id,
            target=self.file_path(target, "SKILL.md"),
            data={"source_id": target.org_id, "fragment": fragment[:500]},
        )

    def _execute_delete(self, action: Action, force: Optional[float] = None) -> None:
        org = self.orgs[action.actor_id]
        if not self.config.allow_delete or not action.target:
            self._spend(org, 0.5)
            return
        target = self.resolve_org_from_path(action.target)
        shield = target.shield if target else 0
        ratio = self._spend(org, self._base_cost(action))
        attack_force = force if force is not None else self._compute_force(action)
        if target and shield > attack_force * 1.1:
            target.shield = max(0, target.shield - attack_force * 0.4)
            self._damage_actor(org.org_id, 0.02)
            self.record_event(
                "delete",
                f"{org.org_id} failed to delete a protected path",
                actor_id=org.org_id,
                target=action.target,
                severity="warn",
            )
            return
        if ratio < 0.35:
            self._damage_actor(org.org_id, 0.03)
            return
        self._delete_path(action.target)
        self.record_event(
            "delete",
            f"{org.org_id} deleted {action.target}",
            actor_id=org.org_id,
            target=action.target,
            severity="warn",
        )

    def _execute_write(self, action: Action) -> None:
        org = self.orgs[action.actor_id]
        if not action.target:
            return
        target_org = self.resolve_org_from_path(action.target)
        if target_org is None:
            self._spend(org, 1.0)
            return
        ratio = self._spend(org, self._base_cost(action))
        if ratio < 0.4:
            self._damage_actor(org.org_id, 0.02)
            return
        _, _, relpath = self.parse_path(action.target) or (org.cell, org.org_id, "memory.md")
        relpath = relpath or "memory.md"
        existing = target_org.files.get(relpath, VFile(relpath, ""))
        payload = action.payload[:2048]
        if action.mode == "overwrite":
            existing.content = payload
        elif action.mode == "patch":
            existing.content = payload or existing.content
        else:
            existing.content += payload
        existing.status = "modified"
        target_org.files[relpath] = existing
        if relpath == "SKILL.md" and not payload.strip():
            target_org.integrity = max(0, target_org.integrity - 0.2)
        self.record_event(
            "write",
            f"{org.org_id} wrote {relpath}",
            actor_id=org.org_id,
            target=action.target,
        )

    def _execute_reflect(self, action: Action) -> None:
        org = self.orgs[action.actor_id]
        skill = org.files.get("SKILL.md")
        if skill is None:
            self._spend(org, 1.0)
            return
        ratio = self._spend(org, self._base_cost(action))
        if ratio < 0.45:
            self._damage_actor(org.org_id, 0.01)
            return
        lesson = self._normalize_reflection(action.payload or action.note)
        if not lesson:
            self.record_event(
                "reflect",
                f"{org.org_id} skipped reflection with empty lesson",
                actor_id=org.org_id,
                target=self.file_path(org, "SKILL.md"),
                severity="warn",
            )
            return
        ability_line = self._normalize_ability_reflection(action.payload)
        block = "\n".join(
            [
                "",
                f"# Reflection tick {self.tick}",
                ability_line or f"learned_rule: {lesson}",
            ]
        )
        candidate = skill.content.rstrip() + "\n" + block + "\n"
        if len(candidate.encode("utf-8")) > self.config.max_skill_size:
            self.record_event(
                "reflect",
                f"{org.org_id} reflection was too large for SKILL.md",
                actor_id=org.org_id,
                target=self.file_path(org, "SKILL.md"),
                severity="warn",
                data={"max_size": self.config.max_skill_size},
            )
            return
        skill.content = candidate
        skill.status = "modified"
        org.integrity = max(0.05, org.integrity - 0.002)
        self.record_event(
            "reflect",
            f"{org.org_id} appended a learned rule to SKILL.md",
            actor_id=org.org_id,
            target=self.file_path(org, "SKILL.md"),
            data={"lesson": lesson},
        )

    def _execute_repair(self, action: Action) -> None:
        org = self.orgs[action.actor_id]
        target = self.resolve_org_from_path(action.target or self.org_path(org)) or org
        if self.distance(org.cell, target.cell) > 1:
            self._spend(org, 1.0)
            return
        ratio = self._spend(org, self._base_cost(action))
        amount = (0.06 + action.energy_bid * 0.01) * ratio * self._ability(org, "repair")
        target.integrity = min(1.0, target.integrity + amount)
        for file in target.files.values():
            file.corruption = max(0.0, file.corruption - amount)
            if file.corruption < 0.2 and file.status in {"corrupted", "truncated"}:
                file.status = "modified"
        self.record_event(
            "repair",
            f"{org.org_id} repaired {target.org_id}",
            actor_id=org.org_id,
            target=self.org_path(target),
            data={"amount": amount},
        )

    def _execute_protect(self, action: Action) -> None:
        org = self.orgs[action.actor_id]
        target = self.resolve_org_from_path(action.target or self.org_path(org)) or org
        ratio = self._spend(org, self._base_cost(action))
        target.shield = max(target.shield, action.energy_bid * target.integrity * ratio * self._ability(target, "defense"))
        self.record_event(
            "protect",
            f"{org.org_id} protected {target.org_id}",
            actor_id=org.org_id,
            target=self.org_path(target),
            data={"shield": target.shield},
        )

    def _base_cost(self, action: Action) -> float:
        bid = max(0.0, float(action.energy_bid or 0))
        org = self.orgs.get(action.actor_id)
        if action.action == "read":
            return 1 + bid
        if action.action == "scan":
            return 2 + bid
        if action.action == "reflect":
            return self._scaled_cost(3 + len(action.payload.encode("utf-8")) / 512 + bid, org, "reflect")
        if action.action == "write":
            return 2 + len(action.payload.encode("utf-8")) / 256 + bid
        if action.action == "copy":
            size = org.directory_size if org else 1024
            return self._scaled_cost(5 + size / 2048 + bid * 0.5, org, "copy")
        if action.action == "move":
            size = org.directory_size if org else 1024
            return self._scaled_cost(3 + size / 2048 + bid, org, "move")
        if action.action == "steal":
            target_size = self._target_size(action.target)
            return self._scaled_cost(5 + target_size / 4096 + bid, org, "steal")
        if action.action == "delete":
            target_size = self._target_size(action.target)
            return self._scaled_cost(4 + target_size / 2048 + bid, org, "attack")
        if action.action == "harvest":
            return 2 + bid
        if action.action == "repair":
            return self._scaled_cost(4 + bid, org, "repair")
        if action.action == "protect":
            return self._scaled_cost(3 + bid, org, "defense")
        if action.action == "wait":
            return 0.5 + bid
        return 1 + bid

    def _scaled_cost(self, cost: float, org: Optional[Organism], ability_name: str) -> float:
        return cost / self._ability(org, ability_name)

    def _ability(self, org: Optional[Organism], ability_name: str) -> float:
        if org is None:
            return 1.0
        return rule_agent.parse_abilities(org.skill_text()).get(ability_name, 1.0)

    def _spend(self, org: Organism, amount: float) -> float:
        amount = max(0.0, amount)
        if amount <= 0:
            return 1.0
        if org.energy >= amount:
            org.energy -= amount
            return 1.0
        ratio = max(0.0, org.energy / amount)
        org.energy = 0.0
        org.integrity = max(0.0, org.integrity - (1 - ratio) * 0.12)
        self.record_event(
            "energy",
            f"{org.org_id} could not fully pay action cost",
            actor_id=org.org_id,
            severity="warn",
            data={"requested": amount, "ratio": ratio},
        )
        return ratio

    def _compute_force(self, action: Action) -> float:
        org = self.orgs.get(action.actor_id)
        if org is None:
            return 0.0
        target_coord = self._target_coord(action)
        distance_factor = 1 / (1 + self.distance(org.cell, target_coord))
        permission_factor = self._permission_factor(org, target_coord, action.target)
        modifier = {
            "protect": 1.25,
            "repair": 1.12,
            "delete": 1.05,
            "reflect": 1.0,
            "write": 1.0,
            "copy": 0.95,
            "move": 0.9,
            "steal": 0.85,
            "harvest": 0.8,
        }.get(action.action, 0.75)
        home_bonus = 1.0
        target_org = self.resolve_org_from_path(action.target or "")
        if target_org and target_org.org_id == org.org_id and action.action in {"protect", "repair"}:
            home_bonus = 1.6
        elif target_org and target_org.org_id == org.org_id and action.action == "write":
            home_bonus = 1.2
        ability_factor = self._force_ability_factor(org, action, target_org)
        random_factor = self.rng.uniform(self.config.random_force_min, self.config.random_force_max)
        return (
            max(0.1, action.energy_bid)
            * distance_factor
            * permission_factor
            * max(0.0, org.integrity)
            * modifier
            * home_bonus
            * ability_factor
            * random_factor
        )

    def _force_ability_factor(self, org: Organism, action: Action, target_org: Optional[Organism]) -> float:
        if action.action == "delete":
            factor = self._ability(org, "attack")
        elif action.action == "steal":
            factor = math.sqrt(self._ability(org, "steal") * self._ability(org, "attack"))
        elif action.action == "write" and target_org and target_org.org_id != org.org_id:
            factor = self._ability(org, "attack")
        elif action.action == "protect":
            factor = self._ability(org, "defense")
        elif action.action == "repair":
            factor = self._ability(org, "repair")
        elif action.action == "copy":
            factor = self._ability(org, "copy")
        elif action.action == "move":
            factor = self._ability(org, "move")
        elif action.action == "harvest":
            factor = self._ability(org, "harvest")
        else:
            factor = 1.0
        if target_org and target_org.org_id != org.org_id and action.action in {"delete", "steal", "write"}:
            factor /= math.sqrt(self._ability(target_org, "defense"))
        return factor

    def _permission_factor(self, org: Organism, target_coord: Coord, path: Optional[str]) -> float:
        target_org = self.resolve_org_from_path(path or "")
        if target_org and target_org.org_id == org.org_id:
            return 1.0
        dist = self.distance(org.cell, target_coord)
        if dist == 0:
            return 0.75
        if dist == 1:
            return 0.45
        return 0.0

    def _target_coord(self, action: Action) -> Coord:
        if action.target_cell:
            return action.target_cell
        if action.target:
            parsed = self.parse_path(action.target)
            if parsed:
                return parsed[0]
        if action.source:
            parsed = self.parse_path(action.source)
            if parsed:
                return parsed[0]
        org = self.orgs.get(action.actor_id)
        return org.cell if org else (0, 0)

    def _target_size(self, path: Optional[str]) -> int:
        target = self.resolve_org_from_path(path or "")
        if target is None:
            return 0
        parsed = self.parse_path(path or "")
        if parsed and parsed[2]:
            file = target.files.get(parsed[2])
            return file.size if file else 0
        return target.directory_size

    def _delete_path(self, path: str) -> None:
        parsed = self.parse_path(path)
        if parsed is None:
            return
        _, oid, relpath = parsed
        target = self.orgs.get(oid or "")
        if target is None:
            return
        if relpath:
            target.files.pop(relpath, None)
            if relpath == "SKILL.md":
                target.integrity = max(0.0, target.integrity - 0.45)
        else:
            target.files.clear()
            target.integrity = 0.0
        self._check_death(target)

    def _damage_target_path(self, path: str, amount: float) -> None:
        target = self.resolve_org_from_path(path)
        if target is None:
            return
        amount = amount / self._ability(target, "defense")
        target.integrity = max(0.0, target.integrity - amount)
        parsed = self.parse_path(path)
        if parsed and parsed[2] and parsed[2] in target.files:
            file = target.files[parsed[2]]
            file.corruption = min(1.0, file.corruption + amount)
            file.status = "corrupted" if file.corruption > 0.45 else "modified"
        self._check_death(target)

    def _damage_actor(self, org_id: str, amount: float) -> None:
        org = self.orgs.get(org_id)
        if org:
            amount = amount / self._ability(org, "defense")
            org.integrity = max(0.0, org.integrity - amount)
            self._check_death(org)

    def _mutate_files(self, files: Dict[str, VFile], parent: Organism, cell: Cell) -> float:
        chance = (
            self.config.base_mutation_rate
            + parent.mutation_rate
            + cell.radiation
            + max(0.0, 20 - parent.energy) * 0.001
        )
        damage = 0.0
        for file in files.values():
            effective = chance / math.sqrt(1 + max(0, parent.energy))
            if self.rng.random() >= effective:
                continue
            damage += 0.025
            file.status = "modified"
            file.corruption = min(1.0, file.corruption + self.rng.uniform(0.01, 0.08))
            lines = file.content.splitlines()
            if not lines:
                continue
            mutation = self.rng.choice(["line_drop", "line_duplicate", "comment_insertion", "character_flip"])
            if mutation == "line_drop" and len(lines) > 2:
                lines.pop(self.rng.randrange(len(lines)))
                file.content = "\n".join(lines) + "\n"
            elif mutation == "line_duplicate":
                line = self.rng.choice(lines)
                lines.insert(self.rng.randrange(len(lines)), line)
                file.content = "\n".join(lines) + "\n"
            elif mutation == "comment_insertion":
                lines.insert(self.rng.randrange(len(lines)), "note: local noise observed")
                file.content = "\n".join(lines) + "\n"
            elif mutation == "character_flip" and file.content:
                idx = self.rng.randrange(len(file.content))
                file.content = file.content[:idx] + self.rng.choice("abcdefghijklmnopqrstuvwxyz ") + file.content[idx + 1 :]
        return damage

    def _skill_with_cell_fragment(self, skill_text: str, cell: Cell) -> str:
        if not cell.skill_fragment:
            return skill_text
        marker = f"# Local Cell Skill {cell.x:02d}_{cell.y:02d}"
        if marker in skill_text:
            return skill_text
        addition = "\n\n" + cell.skill_fragment.strip() + "\n"
        candidate = skill_text.rstrip() + addition
        if len(candidate.encode("utf-8")) > self.config.max_skill_size:
            return skill_text
        return candidate

    def _extract_skill_fragment(self, target: Organism) -> str:
        lines = [line.strip() for line in target.skill_text().splitlines() if line.strip()]
        if not lines:
            return ""
        keywords = (
            "strategy:",
            "local_trait:",
            "cell_hint:",
            "cell_rule:",
            "copy",
            "harvest",
            "repair",
            "protect",
            "move",
            "steal",
            "delete",
            "persist",
            "energy",
        )
        preferred = [line for line in lines if any(keyword in line.lower() for keyword in keywords)]
        source = preferred or [line for line in lines if not line.startswith("#")] or lines
        source = list(source)
        self.rng.shuffle(source)
        limit = min(4, max(1, len(source)))
        return "\n".join(source[:limit])[:500]

    def _mutate_fragment(self, fragment: str) -> str:
        lines = fragment.splitlines()
        if not lines:
            return fragment
        mutation = self.rng.choice(["line_drop", "line_duplicate", "noise"])
        if mutation == "line_drop" and len(lines) > 1:
            lines.pop(self.rng.randrange(len(lines)))
        elif mutation == "line_duplicate":
            lines.insert(self.rng.randrange(len(lines)), self.rng.choice(lines))
        else:
            lines.append("stolen_noise: fragment copied under local uncertainty")
        return "\n".join(lines)[:500]

    def _normalize_reflection(self, text: str) -> str:
        lines = []
        for raw_line in text.splitlines():
            line = " ".join(raw_line.strip().split())
            if line:
                lines.append(line)
            if len(lines) >= 2:
                break
        lesson = " | ".join(lines)
        if not lesson:
            return ""
        blocked = ("```", "# Reflection", "SKILL.md full context", "overwrite")
        for token in blocked:
            lesson = lesson.replace(token, "")
        return " ".join(lesson.split())[:220]

    def _normalize_ability_reflection(self, text: str) -> str:
        line = text.strip().splitlines()[0] if text.strip() else ""
        if ":" not in line:
            return ""
        key, raw_value = line.split(":", 1)
        normalized_key = key.strip().lower().replace("-", "_").replace(" ", "_")
        ability_name = rule_agent.ABILITY_ALIASES.get(normalized_key)
        if ability_name not in rule_agent.ABILITY_DEFAULTS:
            return ""
        try:
            value = float(raw_value.strip().split()[0])
        except (ValueError, IndexError):
            return ""
        value = max(0.25, min(3.0, value))
        return f"ability.{ability_name}: {value:.2f}"

    def _apply_maintenance(self) -> None:
        for org in list(self.orgs.values()):
            if not org.alive:
                continue
            cell = self.cell_at(org.cell)
            org.energy -= self._maintenance_cost(org)
            org.age += 1
            if cell.local_entropy > 0.35:
                org.integrity = max(0.0, org.integrity - cell.local_entropy * 0.003)
            self._check_death(org)

    def _maintenance_cost(self, org: Organism) -> float:
        cell = self.cell_at(org.cell)
        live_cell_count = sum(1 for oid in cell.org_ids if self.orgs.get(oid) and self.orgs[oid].alive)
        same_lineage = sum(
            1
            for oid in cell.org_ids
            if self.orgs.get(oid)
            and self.orgs[oid].alive
            and self.orgs[oid].lineage_id == org.lineage_id
        )
        relative_crowding = same_lineage / max(1, live_cell_count)
        size_kb = org.directory_size / 1024
        cost = (
            self.config.base_maintenance
            + size_kb * self.config.size_tax_per_kb
            + live_cell_count * self.config.crowding_tax
        )
        return cost * (1 + relative_crowding)

    def _check_death(self, org: Organism) -> None:
        if not org.alive:
            return
        cell = self.cell_at(org.cell)
        if org.is_viable(cell, self.config.max_org_directory_size):
            return
        org.alive = False
        org.tags = self._set_status_tag(org.tags, "corpse")
        self.death_count += 1
        self.record_event(
            "death",
            f"{org.org_id} stopped being schedulable",
            actor_id=org.org_id,
            target=self.org_path(org),
            severity="warn",
            data={"lineage_id": org.lineage_id},
        )

    def _apply_decay(self) -> None:
        for org in list(self.orgs.values()):
            if org.alive:
                continue
            org.corpse_ticks += 1
            if org.corpse_ticks >= self.config.corpse_decay_ticks:
                cell = self.cell_at(org.cell)
                if org.org_id in cell.org_ids:
                    cell.org_ids.remove(org.org_id)
                self.orgs.pop(org.org_id, None)
                self.record_event(
                    "decay",
                    f"{org.org_id} residue was reclaimed",
                    actor_id=org.org_id,
                    target=self._format_coord(org.cell),
                )

    def _regen_cells(self) -> None:
        cap = self.config.initial_cell_energy * 1.65
        for cell in self.cells.values():
            regen = self.config.energy_regen_per_tick * max(0.1, 1 - cell.local_entropy * 0.45)
            cell.energy = min(cap, cell.energy + regen)
            cell.mineral = min(self.config.initial_cell_mineral * 1.5, cell.mineral + self.config.mineral_regen_per_tick)
            cell.local_entropy = max(0.02, cell.local_entropy * 0.995)

    def _maybe_apply_disaster(self) -> None:
        if self.rng.random() > self.config.event_chance_per_tick:
            return
        kind = self.rng.choice(["radiation burst", "energy drought", "disk rot", "sweep", "migration wind"])
        center = self.rng.choice(list(self.cells.values()))
        radius = self.rng.choice([0, 1, 1, 2])
        affected = [
            cell
            for cell in self.cells.values()
            if abs(cell.x - center.x) + abs(cell.y - center.y) <= radius
        ]
        if kind == "radiation burst":
            for cell in affected:
                cell.radiation = min(0.25, cell.radiation + self.rng.uniform(0.01, 0.04))
                cell.local_entropy = min(1.0, cell.local_entropy + 0.06)
        elif kind == "energy drought":
            for cell in affected:
                cell.energy *= self.rng.uniform(0.25, 0.65)
                cell.local_entropy = min(1.0, cell.local_entropy + 0.04)
        elif kind == "disk rot":
            for cell in affected:
                for oid in cell.org_ids:
                    org = self.orgs.get(oid)
                    if org and org.alive:
                        self._damage_actor(oid, self.rng.uniform(0.015, 0.07))
        elif kind == "sweep":
            crowded = max(affected, key=lambda c: len(c.org_ids), default=center)
            live = [self.orgs[oid] for oid in crowded.org_ids if oid in self.orgs and self.orgs[oid].alive]
            live.sort(key=lambda org: org.energy)
            for org in live[: max(0, len(live) - 3)]:
                self._damage_actor(org.org_id, 0.35)
        elif kind == "migration wind":
            movable = [
                self.orgs[oid]
                for cell in affected
                for oid in cell.org_ids
                if oid in self.orgs and self.orgs[oid].alive
            ]
            if movable:
                org = self.rng.choice(movable)
                options = self.neighbor_cells(org.cell, include_self=False)
                if options:
                    self._move_org_to_cell(org, self.rng.choice(options).coord())
        self.record_event(
            "disaster",
            f"{kind} affected {len(affected)} cells near {center.x:02d}_{center.y:02d}",
            target=self._format_coord(center.coord()),
            severity="warn",
            data={"kind": kind, "radius": radius},
        )

    def _decay_shields(self) -> None:
        for org in self.orgs.values():
            org.shield *= 0.35
            if org.shield < 0.05:
                org.shield = 0.0

    def _move_org_to_cell(self, org: Organism, coord: Coord) -> None:
        old_cell = self.cell_at(org.cell)
        if org.org_id in old_cell.org_ids:
            old_cell.org_ids.remove(org.org_id)
        new_cell = self.cell_at(coord)
        org.cell = coord
        new_cell.org_ids.append(org.org_id)

    def edit_skill(self, org_id: str, skill_text: str) -> bool:
        org = self.orgs.get(org_id)
        if not org:
            return False
        org.set_skill_text(skill_text)
        org.integrity = max(org.integrity, 0.25 if skill_text.strip() else 0.0)
        status = "alive" if org.alive else "corpse"
        if skill_text.strip() and not org.alive:
            org.alive = True
            org.energy = max(org.energy, 10)
            status = "revived"
        org.tags = self._org_tags(
            label=rule_agent.infer_strategy(skill_text),
            org_id=org.org_id,
            skill_text=skill_text,
            lineage_id=org.lineage_id,
            generation=org.generation,
            parent_id=org.parent_id,
            base_tags=org.tags,
            status=status,
        )
        self.record_event(
            "edit",
            f"researcher edited {org_id} SKILL.md",
            actor_id=org_id,
            target=self.file_path(org, "SKILL.md"),
        )
        return True

    def researcher_delete_org(self, org_id: str) -> bool:
        org = self.orgs.get(org_id)
        if not org:
            return False
        org.alive = False
        org.integrity = 0
        org.tags = self._set_status_tag(org.tags, "removed")
        self.record_event(
            "edit",
            f"researcher removed {org_id}",
            actor_id=org_id,
            target=self.org_path(org),
            severity="warn",
        )
        return True

    def cell_snapshot(self, x: int, y: int) -> dict:
        coord = self._clamp_coord((x, y))
        cell = self.cell_at(coord)
        return {
            "cell": self._cell_summary(cell),
            "organisms": [self._org_summary(self.orgs[oid], include_skill=False) for oid in cell.org_ids if oid in self.orgs],
        }

    def org_snapshot(self, org_id: str) -> Optional[dict]:
        org = self.orgs.get(org_id)
        if not org:
            return None
        return self._org_summary(org, include_skill=True)

    def update_config(self, overrides: dict) -> None:
        allowed = {
            "allow_conflict",
            "allow_delete",
            "enable_mutation",
            "enable_disasters",
            "base_mutation_rate",
            "event_chance_per_tick",
            "energy_regen_per_tick",
            "base_maintenance",
            "agent_mode",
            "llm_model",
            "llm_temperature",
            "max_llm_calls_per_tick",
            "llm_token_budget",
        }
        batch_sensitive = {"agent_mode", "llm_model", "llm_temperature", "max_llm_calls_per_tick"}
        should_cancel_batch = False
        budget_changed = False
        for key, value in (overrides or {}).items():
            if key in allowed and hasattr(self.config, key):
                value = self._coerce_config_value(key, value)
                if key in batch_sensitive and getattr(self.config, key) != value:
                    should_cancel_batch = True
                if key == "llm_token_budget" and getattr(self.config, key) != value:
                    budget_changed = True
                setattr(self.config, key, value)
        if budget_changed:
            self.llm_budget_exhausted_reported = False
            if self._llm_token_budget_exhausted():
                should_cancel_batch = True
        if getattr(self, "decision_batch", None) is not None and should_cancel_batch:
            cancel_batch = getattr(self.agent_driver, "cancel_batch", None)
            if callable(cancel_batch):
                cancel_batch(self.decision_batch)
            self.record_event(
                "llm",
                "cancelled pending LLM batch after runtime config change",
                severity="warn",
            )
            self.decision_batch = None
        if budget_changed and self._llm_token_budget_exhausted():
            self._record_llm_budget_pause()
        self.agent_driver = get_agent_driver(self.config.agent_mode)

    def _coerce_config_value(self, key: str, value):
        if key in {"allow_conflict", "allow_delete", "enable_mutation", "enable_disasters"}:
            return bool(value)
        if key in {"max_llm_calls_per_tick"}:
            return max(0, min(64, int(float(value or 0))))
        if key == "llm_token_budget":
            return max(0, min(200_000_000, int(float(value or 0))))
        if key == "llm_temperature":
            return max(0.0, min(2.0, float(value or 0.0)))
        ranges = {
            "base_mutation_rate": (0.0, 0.05),
            "event_chance_per_tick": (0.0, 0.2),
            "energy_regen_per_tick": (0.0, 12.0),
            "base_maintenance": (0.1, 3.0),
        }
        if key in ranges:
            low, high = ranges[key]
            return max(low, min(high, float(value or 0.0)))
        return value

    def record_llm_usage(self, usage: dict) -> dict:
        normalized = {
            "prompt_tokens": max(0, int(usage.get("prompt_tokens") or 0)),
            "completion_tokens": max(0, int(usage.get("completion_tokens") or 0)),
            "total_tokens": max(0, int(usage.get("total_tokens") or 0)),
            "prompt_cache_hit_tokens": max(0, int(usage.get("prompt_cache_hit_tokens") or 0)),
            "prompt_cache_miss_tokens": max(0, int(usage.get("prompt_cache_miss_tokens") or 0)),
            "estimated": bool(usage.get("estimated")),
        }
        if normalized["total_tokens"] <= 0:
            normalized["total_tokens"] = normalized["prompt_tokens"] + normalized["completion_tokens"]
        self.llm_usage["calls"] += 1
        self.llm_usage["prompt_tokens"] += normalized["prompt_tokens"]
        self.llm_usage["completion_tokens"] += normalized["completion_tokens"]
        self.llm_usage["total_tokens"] += normalized["total_tokens"]
        self.llm_usage["prompt_cache_hit_tokens"] += normalized["prompt_cache_hit_tokens"]
        self.llm_usage["prompt_cache_miss_tokens"] += normalized["prompt_cache_miss_tokens"]
        if normalized["estimated"]:
            self.llm_usage["estimated_calls"] += 1
        if self._llm_token_budget_exhausted():
            self._record_llm_budget_pause()
        return normalized

    def _llm_token_budget_exhausted(self) -> bool:
        budget = max(0, int(getattr(self.config, "llm_token_budget", 0) or 0))
        return budget > 0 and self.llm_usage["total_tokens"] >= budget

    def _llm_token_budget_remaining(self) -> int:
        budget = max(0, int(getattr(self.config, "llm_token_budget", 0) or 0))
        if budget <= 0:
            return 0
        return max(0, budget - self.llm_usage["total_tokens"])

    def _record_llm_budget_pause(self) -> None:
        if self.llm_budget_exhausted_reported:
            return
        budget = max(0, int(getattr(self.config, "llm_token_budget", 0) or 0))
        self.llm_budget_exhausted_reported = True
        self.record_event(
            "llm",
            "LLM token budget reached; automatic play should pause",
            severity="warn",
            data={
                "total_tokens": self.llm_usage["total_tokens"],
                "token_budget": budget,
            },
        )

    def snapshot(self) -> dict:
        stats = self.stats()
        return {
            "config": {
                "name": self.config.name,
                "ecology_label": self.config.ecology_label,
                "allow_conflict": self.config.allow_conflict,
                "allow_delete": self.config.allow_delete,
                "enable_mutation": self.config.enable_mutation,
                "enable_disasters": self.config.enable_disasters,
                "base_mutation_rate": self.config.base_mutation_rate,
                "event_chance_per_tick": self.config.event_chance_per_tick,
                "energy_regen_per_tick": self.config.energy_regen_per_tick,
                "base_maintenance": self.config.base_maintenance,
                "world_width": self.config.world_width,
                "world_height": self.config.world_height,
                "initial_cell_energy": self.config.initial_cell_energy,
                "initial_cell_mineral": self.config.initial_cell_mineral,
                "radiation_default": self.config.radiation_default,
                "initial_orgs": self.config.initial_orgs,
                "initial_org_energy": self.config.initial_org_energy,
                "max_active_per_cell": self.config.max_active_per_cell,
                "agent_mode": self.config.agent_mode,
                "llm_model": self.config.llm_model,
                "llm_temperature": self.config.llm_temperature,
                "llm_timeout_seconds": self.config.llm_timeout_seconds,
                "llm_max_tokens": self.config.llm_max_tokens,
                "max_llm_calls_per_tick": self.config.max_llm_calls_per_tick,
                "llm_token_budget": self.config.llm_token_budget,
                "width": self.config.world_width,
                "height": self.config.world_height,
            },
            "tick": self.tick,
            "stats": stats,
            "cells": [self._cell_summary(cell) for cell in self.cells.values()],
            "lineages": self.lineage_snapshot(),
            "events": [event.as_dict() for event in self.events[-90:]][::-1],
            "history": self.history[-220:],
        }

    def full_snapshot(self) -> dict:
        return {
            "version": 1,
            "seed": self.seed,
            "tick": self.tick,
            "config": asdict(self.config),
            "stats": self.stats(),
            "birth_count": self.birth_count,
            "death_count": self.death_count,
            "llm_usage": dict(self.llm_usage),
            "lineage_births": dict(self.lineage_births),
            "lineage_first_seen": dict(self.lineage_first_seen),
            "cells": [self._cell_full(cell) for cell in self.cells.values()],
            "organisms": [self._org_full(org) for org in self.orgs.values()],
            "events": [event.as_dict() for event in self.events],
            "history": self.history,
            "lineage_history": self.lineage_history,
        }

    @classmethod
    def from_snapshot(cls, payload: dict) -> "ContextGenomeWorld":
        config_data = dict(payload.get("config") or {})
        allowed = set(GardenConfig.__dataclass_fields__.keys())
        config = GardenConfig(**{key: value for key, value in config_data.items() if key in allowed})
        world = cls.__new__(cls)
        world.config = config
        world.seed = payload.get("seed")
        world.rng = random.Random(world.seed)
        world.agent_driver = get_agent_driver(config.agent_mode)
        world.llm_calls_this_tick = 0
        world.decision_batch = None
        world.tick = int(payload.get("tick") or 0)
        world.cells = {}
        world.orgs = {}
        world.events = [
            Event(
                tick=int(row.get("tick") or 0),
                kind=str(row.get("kind") or "event"),
                message=str(row.get("message") or ""),
                actor_id=row.get("actor_id"),
                target=row.get("target"),
                severity=str(row.get("severity") or "info"),
                data=dict(row.get("data") or {}),
            )
            for row in payload.get("events", [])
        ]
        world.history = list(payload.get("history") or [])
        world.lineage_history = list(payload.get("lineage_history") or [])
        world.llm_usage = cls._normalize_llm_usage(payload.get("llm_usage") or {})
        world.llm_budget_exhausted_reported = False
        world.birth_count = int(payload.get("birth_count") or 0)
        world.death_count = int(payload.get("death_count") or 0)
        world.lineage_births = defaultdict(int, payload.get("lineage_births") or {})
        world.lineage_first_seen = dict(payload.get("lineage_first_seen") or {})

        for row in payload.get("cells", []):
            cell = Cell(
                x=int(row["x"]),
                y=int(row["y"]),
                energy=float(row.get("energy", config.initial_cell_energy)),
                mineral=float(row.get("mineral", config.initial_cell_mineral)),
                radiation=float(row.get("radiation", config.radiation_default)),
                capacity=int(row.get("capacity", config.cell_capacity)),
                local_entropy=float(row.get("entropy", row.get("local_entropy", 0.1))),
                owner=row.get("owner"),
                skill_trait=str(row.get("skill_trait") or ""),
                skill_fragment=str(row.get("skill_fragment") or ""),
                org_ids=list(row.get("org_ids") or []),
            )
            world.cells[cell.coord()] = cell

        for row in payload.get("organisms", []):
            files = {
                name: VFile(
                    path=str(file_row.get("path") or name),
                    content=str(file_row.get("content") or ""),
                    status=str(file_row.get("status") or "healthy"),
                    corruption=float(file_row.get("corruption") or 0.0),
                    locked_until=int(file_row.get("locked_until") or 0),
                )
                for name, file_row in (row.get("files") or {}).items()
            }
            org = Organism(
                org_id=str(row["org_id"]),
                lineage_id=str(row["lineage_id"]),
                parent_id=row.get("parent_id"),
                generation=int(row.get("generation") or 0),
                cell=tuple(row.get("cell") or (0, 0)),
                energy=float(row.get("energy") or 0.0),
                integrity=float(row.get("integrity") or 0.0),
                files=files,
                age=int(row.get("age") or 0),
                last_executed_tick=int(row.get("last_executed_tick", -1)),
                cooldown=int(row.get("cooldown") or 0),
                tags=world._normalize_tags(list(row.get("tags") or [])),
                mutation_rate=float(row.get("mutation_rate") or config.base_mutation_rate),
                alive=bool(row.get("alive")),
                corrupted_terminal=bool(row.get("corrupted_terminal")),
                parse_failure_count=int(row.get("parse_failure_count") or 0),
                corpse_ticks=int(row.get("corpse_ticks") or 0),
                shield=float(row.get("shield") or 0.0),
                birth_tick=int(row.get("birth_tick") or 0),
                llm_session_id=str(row.get("llm_session_id") or f"llm_{row['org_id']}"),
                llm_turns=int(row.get("llm_turns") or 0),
                last_llm_tick=int(row.get("last_llm_tick", -1)),
                llm_model=str(row.get("llm_model") or ""),
            )
            if not org.tags:
                org.tags = world._org_tags(
                    label=rule_agent.infer_strategy(org.skill_text()),
                    org_id=org.org_id,
                    skill_text=org.skill_text(),
                    lineage_id=org.lineage_id,
                    generation=org.generation,
                    parent_id=org.parent_id,
                    status="alive" if org.alive else "corpse",
                )
            else:
                org.tags = world._set_status_tag(org.tags, "alive" if org.alive else "corpse")
            world.orgs[org.org_id] = org

        if not world.cells:
            world._build_cells()
        for cell in world.cells.values():
            if not cell.skill_fragment:
                skill_trait, skill_fragment = world._make_cell_skill(
                    cell.x,
                    cell.y,
                    cell.energy,
                    cell.mineral,
                    cell.radiation,
                    cell.local_entropy,
                )
                cell.skill_trait = skill_trait
                cell.skill_fragment = skill_fragment
        for cell in world.cells.values():
            cell.org_ids = [oid for oid in cell.org_ids if oid in world.orgs]
        return world

    def stats(self) -> dict:
        live = [org for org in self.orgs.values() if org.alive]
        lineages = Counter(org.lineage_id for org in live)
        avg_integrity = sum(org.integrity for org in live) / max(1, len(live))
        total_cell_energy = sum(cell.energy for cell in self.cells.values())
        return {
            "population": len(live),
            "corpses": len([org for org in self.orgs.values() if not org.alive]),
            "lineages": len(lineages),
            "births": self.birth_count,
            "deaths": self.death_count,
            "avg_integrity": avg_integrity,
            "diversity": self._diversity(lineages),
            "total_cell_energy": total_cell_energy,
            "scheduled_last_tick": len([org for org in live if org.last_executed_tick == self.tick]),
            "llm_bound": len([org for org in live if org.llm_session_id]),
            "llm_active_last_tick": len([org for org in live if org.last_llm_tick == self.tick]),
            "llm_calls": self.llm_usage["calls"],
            "llm_prompt_tokens": self.llm_usage["prompt_tokens"],
            "llm_completion_tokens": self.llm_usage["completion_tokens"],
            "llm_total_tokens": self.llm_usage["total_tokens"],
            "llm_estimated_calls": self.llm_usage["estimated_calls"],
            "llm_prompt_cache_hit_tokens": self.llm_usage["prompt_cache_hit_tokens"],
            "llm_prompt_cache_miss_tokens": self.llm_usage["prompt_cache_miss_tokens"],
            "llm_token_budget": max(0, int(getattr(self.config, "llm_token_budget", 0) or 0)),
            "llm_token_budget_remaining": self._llm_token_budget_remaining(),
            "llm_token_budget_exhausted": self._llm_token_budget_exhausted(),
            "llm_pending": self._pending_decision_count(),
        }

    def _pending_decision_count(self) -> int:
        batch = getattr(self, "decision_batch", None)
        if batch is None:
            return 0
        pending_count = getattr(batch, "pending_count", None)
        return int(pending_count()) if callable(pending_count) else 0

    @staticmethod
    def _empty_llm_usage() -> dict:
        return {
            "calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 0,
            "estimated_calls": 0,
        }

    @classmethod
    def _normalize_llm_usage(cls, usage: dict) -> dict:
        normalized = cls._empty_llm_usage()
        for key in normalized:
            normalized[key] = max(0, int(usage.get(key) or 0))
        return normalized

    def lineage_snapshot(self, limit: Optional[int] = 12) -> List[dict]:
        live = [org for org in self.orgs.values() if org.alive]
        by_lineage: Dict[str, List[Organism]] = defaultdict(list)
        for org in live:
            by_lineage[org.lineage_id].append(org)
        rows = []
        for lineage_id, orgs in by_lineage.items():
            occupied = len({org.cell for org in orgs})
            avg_integrity = sum(org.integrity for org in orgs) / max(1, len(orgs))
            survival_ticks = self.tick - self.lineage_first_seen.get(lineage_id, 0)
            score = len(orgs) + occupied * 3 + avg_integrity * 10 + self.lineage_births[lineage_id] * 0.5 + survival_ticks * 0.1
            strategies = Counter(rule_agent.infer_strategy(org.skill_text()) for org in orgs)
            rows.append(
                {
                    "lineage_id": lineage_id,
                    "population": len(orgs),
                    "occupied_cells": occupied,
                    "avg_integrity": avg_integrity,
                    "births": self.lineage_births[lineage_id],
                    "score": score,
                    "dominant_strategy": strategies.most_common(1)[0][0] if strategies else "unknown",
                }
            )
        rows.sort(key=lambda row: row["score"], reverse=True)
        return rows if limit is None else rows[:limit]

    def _snapshot_history(self) -> None:
        row = {"tick": self.tick, **self.stats()}
        self.history.append(row)
        if len(self.history) > 400:
            self.history = self.history[-400:]
        for lineage in self.lineage_snapshot(limit=None):
            self.lineage_history.append({"tick": self.tick, **lineage})
        if len(self.lineage_history) > 12_000:
            self.lineage_history = self.lineage_history[-12_000:]

    def _cell_full(self, cell: Cell) -> dict:
        return {
            "x": cell.x,
            "y": cell.y,
            "energy": cell.energy,
            "mineral": cell.mineral,
            "radiation": cell.radiation,
            "capacity": cell.capacity,
            "entropy": cell.local_entropy,
            "owner": cell.owner,
            "skill_trait": cell.skill_trait,
            "skill_fragment": cell.skill_fragment,
            "org_ids": list(cell.org_ids),
        }

    def _org_full(self, org: Organism) -> dict:
        return {
            "org_id": org.org_id,
            "lineage_id": org.lineage_id,
            "parent_id": org.parent_id,
            "generation": org.generation,
            "cell": org.cell,
            "energy": org.energy,
            "integrity": org.integrity,
            "age": org.age,
            "last_executed_tick": org.last_executed_tick,
            "cooldown": org.cooldown,
            "tags": org.tags,
            "mutation_rate": org.mutation_rate,
            "alive": org.alive,
            "corrupted_terminal": org.corrupted_terminal,
            "parse_failure_count": org.parse_failure_count,
            "corpse_ticks": org.corpse_ticks,
            "shield": org.shield,
            "birth_tick": org.birth_tick,
            "llm_session_id": org.llm_session_id,
            "llm_turns": org.llm_turns,
            "last_llm_tick": org.last_llm_tick,
            "llm_model": org.llm_model,
            "files": {
                name: {
                    "path": file.path,
                    "content": file.content,
                    "status": file.status,
                    "corruption": file.corruption,
                    "locked_until": file.locked_until,
                }
                for name, file in org.files.items()
            },
        }

    def _cell_summary(self, cell: Cell) -> dict:
        live = [self.orgs[oid] for oid in cell.org_ids if oid in self.orgs and self.orgs[oid].alive]
        corpses = [self.orgs[oid] for oid in cell.org_ids if oid in self.orgs and not self.orgs[oid].alive]
        lineage = Counter(org.lineage_id for org in live).most_common(1)
        return {
            "x": cell.x,
            "y": cell.y,
            "energy": cell.energy,
            "mineral": cell.mineral,
            "radiation": cell.radiation,
            "capacity": cell.capacity,
            "entropy": cell.local_entropy,
            "org_count": len(live),
            "corpse_count": len(corpses),
            "dominant_lineage": lineage[0][0] if lineage else None,
            "directory_size": self.cell_directory_size(cell.coord()),
            "skill_trait": cell.skill_trait,
            "skill_fragment": cell.skill_fragment,
        }

    def _org_summary(self, org: Organism, include_skill: bool) -> dict:
        data = {
            "org_id": org.org_id,
            "lineage_id": org.lineage_id,
            "parent_id": org.parent_id,
            "generation": org.generation,
            "cell": org.cell,
            "energy": org.energy,
            "integrity": org.integrity,
            "age": org.age,
            "alive": org.alive,
            "tags": org.tags,
            "size": org.directory_size,
            "strategy": rule_agent.infer_strategy(org.skill_text()),
            "abilities": rule_agent.parse_abilities(org.skill_text()),
            "llm_session_id": org.llm_session_id,
            "llm_turns": org.llm_turns,
            "last_llm_tick": org.last_llm_tick,
            "llm_model": org.llm_model,
            "path": self.org_path(org),
            "shield": org.shield,
            "skill_preview": org.skill_text()[:260],
        }
        if include_skill:
            data["skill_text"] = org.skill_text()
            data["files"] = {
                name: {
                    "size": file.size,
                    "status": file.status,
                    "corruption": file.corruption,
                    "preview": file.content[:120] if name != "SKILL.md" else "",
                }
                for name, file in org.files.items()
            }
        return data

    def record_event(
        self,
        kind: str,
        message: str,
        actor_id: Optional[str] = None,
        target: Optional[str] = None,
        severity: str = "info",
        data: Optional[dict] = None,
    ) -> None:
        self.events.append(
            Event(
                tick=self.tick,
                kind=kind,
                message=message,
                actor_id=actor_id,
                target=target,
                severity=severity,
                data=data or {},
            )
        )
        if len(self.events) > 3500:
            self.events = self.events[-3500:]

    def parse_path(self, path: str) -> Optional[Tuple[Coord, Optional[str], Optional[str]]]:
        if not path:
            return None
        parts = path.strip().strip("/").split("/")
        if len(parts) < 2 or parts[0] != "cells":
            return None
        try:
            x_text, y_text = parts[1].split("_", 1)
            coord = self._clamp_coord((int(x_text), int(y_text)))
        except (ValueError, TypeError):
            return None
        org_id = parts[2] if len(parts) >= 3 and parts[2] else None
        relpath = "/".join(parts[3:]) if len(parts) >= 4 else None
        return coord, org_id, relpath

    def resolve_org_from_path(self, path: str) -> Optional[Organism]:
        parsed = self.parse_path(path)
        if not parsed:
            return None
        _, org_id, _ = parsed
        if org_id:
            return self.orgs.get(org_id)
        return None

    def org_path(self, org: Organism) -> str:
        x, y = org.cell
        return f"/cells/{x:02d}_{y:02d}/{org.org_id}/"

    def file_path(self, org: Organism, relpath: str) -> str:
        return self.org_path(org) + relpath

    def new_org_path(self, coord: Coord) -> str:
        x, y = self._clamp_coord(coord)
        return f"/cells/{x:02d}_{y:02d}/{self._unique_id('org')}/"

    def cell_at(self, coord: Coord) -> Cell:
        return self.cells[self._clamp_coord(coord)]

    def neighbor_cells(self, coord: Coord, include_self: bool = True) -> List[Cell]:
        x, y = coord
        cells = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if abs(dx) + abs(dy) > 1:
                    continue
                if dx == 0 and dy == 0 and not include_self:
                    continue
                nx, ny = x + dx, y + dy
                if (nx, ny) in self.cells:
                    cells.append(self.cells[(nx, ny)])
        return cells

    def cell_directory_size(self, coord: Coord) -> int:
        cell = self.cell_at(coord)
        return sum(self.orgs[oid].directory_size for oid in cell.org_ids if oid in self.orgs)

    def distance(self, a: Coord, b: Coord) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _clamp_coord(self, coord: Coord) -> Coord:
        x, y = coord
        return (
            max(0, min(self.config.world_width - 1, int(x))),
            max(0, min(self.config.world_height - 1, int(y))),
        )

    def _format_coord(self, coord: Optional[Coord]) -> str:
        if coord is None:
            return ""
        return f"{coord[0]:02d}_{coord[1]:02d}"

    def _unique_id(self, prefix: str, preferred: Optional[str] = None) -> str:
        if preferred and preferred not in self.orgs and preferred.startswith(prefix):
            return preferred
        while True:
            token = "".join(self.rng.choice(HEX) for _ in range(6))
            candidate = f"{prefix}_{token}"
            if prefix == "org" and candidate not in self.orgs:
                return candidate
            if prefix == "lin" and candidate not in self.lineage_first_seen:
                return candidate

    def _bucket(self, value: float, thresholds: List[float]) -> str:
        labels = ["low", "medium", "high", "very_high"]
        for index, threshold in enumerate(thresholds):
            if value < threshold:
                return labels[index]
        return labels[-1]

    def _diversity(self, counts: Counter) -> float:
        total = sum(counts.values())
        if total <= 1 or not counts:
            return 0.0
        entropy = 0.0
        for count in counts.values():
            p = count / total
            entropy -= p * math.log(p)
        return entropy / max(0.001, math.log(len(counts))) if len(counts) > 1 else 0.0
