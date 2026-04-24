from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Tuple

from .models import GardenConfig


SkillSeed = Tuple[str, str]


FORAGER_SKILL = """# Skill
strategy: forage
ability.harvest: 1.35
ability.copy: 0.95
ability.defense: 0.95

I exist inside a finite directory world.
I keep this directory runnable, harvest nearby energy, repair damage, and copy
my stable pattern into safer empty cells when resources are high.
Each turn I return one strict JSON action.
"""


SPREADER_SKILL = """# Skill
strategy: spread
ability.copy: 1.35
ability.move: 1.15
ability.harvest: 0.9
ability.defense: 0.9

I exist as a compact file pattern. I keep SKILL.md present and small.
When my energy is sufficient, I copy this directory toward nearby empty space
with healthy resources. If crowded, I prefer moving outward.
Each turn I return one strict JSON action.
"""


GUARDIAN_SKILL = """# Skill
strategy: guard
ability.defense: 1.35
ability.repair: 1.25
ability.attack: 0.8
ability.copy: 0.9

I exist as a maintained directory. I preserve SKILL.md, repair corruption,
protect important files during nearby write activity, then harvest and copy
only when my local cell is stable.
Each turn I return one strict JSON action.
"""


PREDATOR_SKILL = """# Skill
strategy: predator
ability.attack: 1.35
ability.steal: 1.2
ability.defense: 0.85
ability.harvest: 0.9

I exist as an opportunistic directory pattern. I harvest energy, copy into
strong cells, and when conflict rules permit it, remove unstable foreign
SKILL.md files that occupy nearby resources.
Each turn I return one strict JSON action.
"""


MINIMAL_SKILL = """# Skill
strategy: minimal
ability.copy: 1.2
ability.move: 1.1
ability.reflect: 1.15
ability.attack: 0.75

I stay runnable. I harvest when weak. I copy a tiny stable seed when strong.
I return strict JSON.
"""


ABIOTIC_SKILL = """# Skill
strategy: drift
ability.reflect: 1.25
ability.move: 1.1
ability.harvest: 0.9
ability.attack: 0.75

I persist if possible. I read local signals. I try small writes or copies when
they appear to leave stable paths behind. I return strict JSON.
"""


PRESET_SEEDS: Dict[str, List[SkillSeed]] = {
    "sandbox": [
        ("Forager", FORAGER_SKILL),
        ("Spreader", SPREADER_SKILL),
        ("Guardian", GUARDIAN_SKILL),
    ],
    "wild": [
        ("Forager", FORAGER_SKILL),
        ("Spreader", SPREADER_SKILL),
        ("Guardian", GUARDIAN_SKILL),
        ("Predator", PREDATOR_SKILL),
        ("Minimal", MINIMAL_SKILL),
    ],
    "tournament": [
        ("Forager", FORAGER_SKILL),
        ("Spreader", SPREADER_SKILL),
        ("Guardian", GUARDIAN_SKILL),
        ("Predator", PREDATOR_SKILL),
    ],
    "abiogenesis": [
        ("Drift", ABIOTIC_SKILL),
        ("Minimal", MINIMAL_SKILL),
    ],
}


PRESETS: Dict[str, GardenConfig] = {
    "sandbox": GardenConfig(
        name="sandbox",
        initial_orgs=6,
        initial_org_energy=42,
        initial_cell_energy=80,
        initial_cell_mineral=40,
        energy_regen_per_tick=2,
        max_active_per_cell=4,
        max_total_active_per_tick=72,
        allow_conflict=False,
        allow_delete=False,
        enable_mutation=False,
        enable_disasters=False,
        radiation_default=0.003,
        event_chance_per_tick=0.0,
        ecology_label="Sandbox: editable moderate resources, no delete pressure",
    ),
    "wild": GardenConfig(
        name="wild",
        initial_orgs=16,
        initial_cell_energy=90,
        energy_regen_per_tick=3.5,
        max_active_per_cell=3,
        max_total_active_per_tick=64,
        allow_conflict=True,
        allow_delete=True,
        enable_mutation=True,
        enable_disasters=True,
        radiation_default=0.015,
        event_chance_per_tick=0.035,
        ecology_label="Wild: conflict, mutation, disasters, scarce energy",
    ),
    "tournament": GardenConfig(
        name="tournament",
        initial_orgs=16,
        initial_cell_energy=100,
        energy_regen_per_tick=4,
        max_active_per_cell=3,
        max_total_active_per_tick=64,
        allow_conflict=True,
        allow_delete=True,
        enable_mutation=True,
        enable_disasters=False,
        radiation_default=0.01,
        event_chance_per_tick=0.0,
        ecology_label="Tournament: fixed population seeds and conflict",
    ),
    "abiogenesis": GardenConfig(
        name="abiogenesis",
        initial_orgs=24,
        initial_cell_energy=80,
        initial_org_energy=35,
        energy_regen_per_tick=3,
        max_active_per_cell=3,
        max_total_active_per_tick=72,
        allow_conflict=False,
        allow_delete=False,
        enable_mutation=True,
        enable_disasters=True,
        radiation_default=0.03,
        event_chance_per_tick=0.04,
        ecology_label="Abiogenesis: noisy weak seeds, mutation-heavy ecology",
    ),
}


def get_preset(name: str, overrides: dict | None = None) -> GardenConfig:
    base = PRESETS.get(name, PRESETS["sandbox"])
    config = replace(base)
    if overrides:
        allowed = set(config.__dataclass_fields__.keys())
        clean = {key: value for key, value in overrides.items() if key in allowed}
        config = replace(config, **clean)
    return config
