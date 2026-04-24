from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


Coord = Tuple[int, int]

RUNTIME_FILE_NAMES = {
    "dialogue.jsonl",
    "last_llm_response.json",
    "last_prompt.txt",
    "prompt_state.json",
}


@dataclass
class GardenConfig:
    name: str = "sandbox"
    world_width: int = 16
    world_height: int = 16
    cell_capacity: int = 65_536
    initial_cell_energy: float = 100.0
    initial_cell_mineral: float = 50.0
    energy_regen_per_tick: float = 5.0
    mineral_regen_per_tick: float = 1.0
    max_active_per_cell: int = 3
    max_total_active_per_tick: int = 64
    initial_org_energy: float = 50.0
    initial_orgs: int = 8
    base_maintenance: float = 1.0
    size_tax_per_kb: float = 0.05
    crowding_tax: float = 0.2
    base_mutation_rate: float = 0.005
    radiation_default: float = 0.01
    event_chance_per_tick: float = 0.03
    max_skill_size: int = 12_288
    max_org_directory_size: int = 65_536
    corpse_decay_ticks: int = 20
    same_lineage_threshold: float = 0.82
    hybrid_threshold: float = 0.55
    random_force_min: float = 0.85
    random_force_max: float = 1.15
    allow_conflict: bool = False
    allow_delete: bool = False
    enable_mutation: bool = False
    enable_disasters: bool = False
    agent_mode: str = "llm_json"
    llm_model: str = ""
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = 20.0
    llm_max_tokens: int = 320
    max_llm_calls_per_tick: int = 8
    ecology_label: str = "Sandbox ecology"


@dataclass
class Cell:
    x: int
    y: int
    energy: float
    mineral: float
    radiation: float
    capacity: int
    local_entropy: float = 0.1
    owner: Optional[str] = None
    skill_trait: str = ""
    skill_fragment: str = ""
    org_ids: List[str] = field(default_factory=list)

    def coord(self) -> Coord:
        return (self.x, self.y)


@dataclass
class VFile:
    path: str
    content: str
    status: str = "healthy"
    corruption: float = 0.0
    locked_until: int = 0

    @property
    def size(self) -> int:
        return len(self.content.encode("utf-8"))

    def clone(self) -> "VFile":
        return VFile(
            path=self.path,
            content=self.content,
            status=self.status,
            corruption=self.corruption,
            locked_until=self.locked_until,
        )


@dataclass
class Organism:
    org_id: str
    lineage_id: str
    parent_id: Optional[str]
    generation: int
    cell: Coord
    energy: float
    integrity: float
    files: Dict[str, VFile]
    age: int = 0
    last_executed_tick: int = -1
    cooldown: int = 0
    tags: List[str] = field(default_factory=lambda: ["viable"])
    mutation_rate: float = 0.005
    alive: bool = True
    corrupted_terminal: bool = False
    parse_failure_count: int = 0
    corpse_ticks: int = 0
    shield: float = 0.0
    birth_tick: int = 0
    llm_session_id: str = ""
    llm_turns: int = 0
    last_llm_tick: int = -1
    llm_model: str = ""

    def skill_text(self) -> str:
        file = self.files.get("SKILL.md")
        return file.content if file else ""

    def set_skill_text(self, text: str) -> None:
        self.files["SKILL.md"] = VFile("SKILL.md", text)

    @property
    def directory_size(self) -> int:
        return sum(file.size for name, file in self.files.items() if name not in RUNTIME_FILE_NAMES)

    def clone_files(self) -> Dict[str, VFile]:
        return {name: file.clone() for name, file in self.files.items() if name not in RUNTIME_FILE_NAMES}

    def is_viable(self, cell: Cell, max_org_size: int) -> bool:
        skill = self.files.get("SKILL.md")
        if not self.alive or self.corrupted_terminal:
            return False
        if skill is None or skill.size <= 0:
            return False
        if skill.size > max_org_size:
            return False
        if self.directory_size > min(cell.capacity, max_org_size):
            return False
        return self.energy > 0 and self.integrity > 0


@dataclass
class Action:
    actor_id: str
    action: str
    energy_bid: float = 0.0
    source: Optional[str] = None
    target: Optional[str] = None
    target_cell: Optional[Coord] = None
    resource: Optional[str] = None
    payload: str = ""
    mode: str = "append"
    note: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "action": self.action,
            "energy_bid": self.energy_bid,
            "source": self.source,
            "target": self.target,
            "target_cell": self.target_cell,
            "resource": self.resource,
            "payload": self.payload,
            "mode": self.mode,
            "note": self.note,
        }


@dataclass
class Event:
    tick: int
    kind: str
    message: str
    actor_id: Optional[str] = None
    target: Optional[str] = None
    severity: str = "info"
    data: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "kind": self.kind,
            "message": self.message,
            "actor_id": self.actor_id,
            "target": self.target,
            "severity": self.severity,
            "data": self.data,
        }
