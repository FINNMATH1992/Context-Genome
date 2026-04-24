from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional

from .models import Action, Organism

if TYPE_CHECKING:
    from .world import ContextGenomeWorld


ABILITY_DEFAULTS: Dict[str, float] = {
    "harvest": 1.0,
    "copy": 1.0,
    "move": 1.0,
    "steal": 1.0,
    "attack": 1.0,
    "defense": 1.0,
    "repair": 1.0,
    "reflect": 1.0,
}

ABILITY_ALIASES = {
    "ability.harvest": "harvest",
    "ability_harvest": "harvest",
    "harvest_efficiency": "harvest",
    "gather": "harvest",
    "gather_efficiency": "harvest",
    "ability.copy": "copy",
    "ability_copy": "copy",
    "copy_efficiency": "copy",
    "reproduction": "copy",
    "ability.move": "move",
    "ability_move": "move",
    "mobility": "move",
    "move_efficiency": "move",
    "ability.steal": "steal",
    "ability_steal": "steal",
    "steal_efficiency": "steal",
    "learning": "steal",
    "ability.attack": "attack",
    "ability_attack": "attack",
    "attack_power": "attack",
    "attack": "attack",
    "ability.defense": "defense",
    "ability_defense": "defense",
    "defense": "defense",
    "defense_power": "defense",
    "ability.repair": "repair",
    "ability_repair": "repair",
    "repair_efficiency": "repair",
    "ability.reflect": "reflect",
    "ability_reflect": "reflect",
    "reflect_efficiency": "reflect",
}


def parse_abilities(skill_text: str) -> Dict[str, float]:
    abilities = dict(ABILITY_DEFAULTS)
    for raw_line in skill_text.splitlines():
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        normalized_key = key.strip().lower().replace("-", "_").replace(" ", "_")
        ability_name = ABILITY_ALIASES.get(normalized_key)
        if ability_name not in abilities:
            continue
        try:
            value = float(raw_value.strip().split()[0])
        except (ValueError, IndexError):
            continue
        abilities[ability_name] = max(0.25, min(3.0, value))

    budget = float(len(ABILITY_DEFAULTS))
    total = sum(abilities.values())
    if total > budget:
        scale = budget / total
        abilities = {name: value * scale for name, value in abilities.items()}
    return {name: max(0.45, min(1.75, value)) for name, value in abilities.items()}


def infer_strategy(skill_text: str) -> str:
    text = skill_text.lower()
    for line in text.splitlines():
        if line.lower().startswith("strategy:"):
            return line.split(":", 1)[1].strip().split()[0] or "forage"
    if "delete" in text or "remove" in text or "foreign" in text:
        return "predator"
    if "protect" in text or "repair" in text or "backup" in text:
        return "guard"
    if "copy" in text or "spread" in text:
        return "spread"
    if "small" in text or "tiny" in text or "minimal" in text:
        return "minimal"
    return "forage"


def decide(world: "ContextGenomeWorld", org: Organism, observation: Dict) -> Action:
    strategy = infer_strategy(org.skill_text())
    cell = world.cell_at(org.cell)
    nearby = world.neighbor_cells(org.cell, include_self=False)
    low_energy = org.energy < 24
    high_energy = org.energy > 46
    crowded = len([oid for oid in cell.org_ids if world.orgs.get(oid, org).alive]) > 2

    if org.integrity < 0.58:
        return Action(
            actor_id=org.org_id,
            action="repair",
            target=world.org_path(org),
            energy_bid=7,
            note="repair low integrity",
        )

    if strategy == "guard" and (org.integrity < 0.82 or world.rng.random() < 0.06):
        return Action(
            actor_id=org.org_id,
            action="protect",
            target=world.file_path(org, "SKILL.md"),
            energy_bid=6,
            note="guard skill file",
        )

    if cell.energy < 16 and org.energy > 12:
        target_cell = _best_copy_target(world, org, nearby, crowded=True)
        if target_cell is not None:
            return Action(
                actor_id=org.org_id,
                action="move",
                source=world.org_path(org),
                target=f"/cells/{target_cell[0]:02d}_{target_cell[1]:02d}/{org.org_id}/",
                energy_bid=4,
                note="migrate away from depleted cell",
            )

    if low_energy or cell.energy > 20 and not high_energy and world.rng.random() < 0.72:
        return Action(
            actor_id=org.org_id,
            action="harvest",
            target_cell=org.cell,
            resource="energy",
            energy_bid=3 if low_energy else 2,
            note="harvest local energy",
        )

    if strategy == "predator" and world.config.allow_delete and org.energy > 34:
        target = _nearest_foreign_org(world, org)
        if target is not None and world.rng.random() < 0.45:
            return Action(
                actor_id=org.org_id,
                action="delete",
                target=world.file_path(target, "SKILL.md"),
                energy_bid=9,
                note="remove foreign runnable file",
            )

    if org.energy > 30 and world.rng.random() < 0.16:
        target = _nearest_skill_source(world, org)
        if target is not None:
            return Action(
                actor_id=org.org_id,
                action="steal",
                target=world.file_path(target, "SKILL.md"),
                energy_bid=5,
                note="sample nearby skill fragment",
            )

    copy_threshold = 54
    if strategy == "minimal":
        copy_threshold = 48
    elif strategy == "spread":
        copy_threshold = 52
    elif strategy == "guard":
        copy_threshold = 62

    if org.energy > copy_threshold:
        target_cell = _best_copy_target(world, org, nearby, crowded)
        if target_cell is not None:
            bid = 12 if strategy != "minimal" else 8
            return Action(
                actor_id=org.org_id,
                action="copy",
                source=world.org_path(org),
                target=world.new_org_path(target_cell),
                energy_bid=bid,
                note="copy stable directory",
            )

    if strategy == "forage" and cell.energy > 20 and world.rng.random() < 0.35:
        return Action(
            actor_id=org.org_id,
            action="harvest",
            target_cell=org.cell,
            resource="energy",
            energy_bid=2,
            note="opportunistic harvest",
        )

    if world.rng.random() < 0.2:
        scan_target = max(nearby, key=lambda c: c.energy - len(c.org_ids) * 8, default=cell)
        return Action(
            actor_id=org.org_id,
            action="scan",
            target_cell=scan_target.coord(),
            energy_bid=1,
            note="sample nearby cell",
        )

    return Action(actor_id=org.org_id, action="wait", energy_bid=0, note="stable wait")


def _nearest_foreign_org(world: "ContextGenomeWorld", org: Organism) -> Optional[Organism]:
    candidates: List[Organism] = []
    for cell in [world.cell_at(org.cell), *world.neighbor_cells(org.cell, include_self=False)]:
        for oid in cell.org_ids:
            other = world.orgs.get(oid)
            if other and other.alive and other.lineage_id != org.lineage_id:
                candidates.append(other)
    if not candidates:
        return None
    candidates.sort(key=lambda other: (world.distance(org.cell, other.cell), -other.energy))
    return candidates[0]


def _nearest_skill_source(world: "ContextGenomeWorld", org: Organism) -> Optional[Organism]:
    own_text = org.skill_text()
    candidates: List[Organism] = []
    for cell in [world.cell_at(org.cell), *world.neighbor_cells(org.cell, include_self=False)]:
        for oid in cell.org_ids:
            other = world.orgs.get(oid)
            if not other or not other.alive or other.org_id == org.org_id:
                continue
            if other.skill_text() == own_text:
                continue
            candidates.append(other)
    if not candidates:
        return None
    candidates.sort(key=lambda other: (world.distance(org.cell, other.cell), other.lineage_id == org.lineage_id, -other.generation))
    return candidates[0]


def _best_copy_target(world: "ContextGenomeWorld", org: Organism, nearby, crowded: bool):
    choices = []
    for cell in nearby:
        live_count = len([oid for oid in cell.org_ids if world.orgs.get(oid) and world.orgs[oid].alive])
        size_pressure = world.cell_directory_size(cell.coord()) / max(1, cell.capacity)
        if size_pressure > 0.92:
            continue
        score = cell.energy - live_count * 16 - cell.local_entropy * 25
        if live_count == 0:
            score += 18
        if crowded:
            score += 8
        choices.append((score, cell))
    if not choices:
        return None
    choices.sort(key=lambda item: item[0], reverse=True)
    if choices[0][0] < -5 and not crowded:
        return None
    return choices[0][1].coord()
