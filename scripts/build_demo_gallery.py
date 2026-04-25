from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (ROOT, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from context_genome.engine import ContextGenomeWorld, get_preset
from context_genome.engine import rule_agent
from render_evolution_gif import render_frame


@dataclass(frozen=True)
class DemoCase:
    slug: str
    title: str
    title_zh: str
    preset: str
    seed: int
    ticks: int
    sample_every: int
    width: int
    thesis: str
    thesis_zh: str


CASES = [
    DemoCase(
        slug="sandbox-seed30",
        title="Stable Forager Expansion",
        title_zh="稳定采集扩张",
        preset="sandbox",
        seed=30,
        ticks=220,
        sample_every=4,
        width=520,
        thesis="A moderate ecology favors compact contexts that harvest, repair, and copy once local resources recover.",
        thesis_zh="温和生态更偏好紧凑上下文：先采集和修复，再等局部资源恢复后复制。",
    ),
    DemoCase(
        slug="wild-seed16",
        title="Disaster Pressure Selects Minimal Context",
        title_zh="灾害压力选择最小上下文",
        preset="wild",
        seed=16,
        ticks=220,
        sample_every=4,
        width=520,
        thesis="A noisy world with mutation and disasters can favor smaller contexts that copy quickly and carry less maintenance burden.",
        thesis_zh="带突变和灾害的噪声世界可能偏好更小的上下文：复制更快，维护负担更低。",
    ),
    DemoCase(
        slug="tournament-seed19",
        title="Selection Under Conflict",
        title_zh="冲突压力下的选择",
        preset="tournament",
        seed=19,
        ticks=220,
        sample_every=4,
        width=520,
        thesis="A fixed competitive start rewards contexts that balance spread speed with enough integrity to survive crowding.",
        thesis_zh="固定竞争开局会奖励能在扩张速度和拥挤生存之间取得平衡的上下文。",
    ),
]


def main() -> None:
    image_dir = ROOT / "docs" / "images"
    example_dir = ROOT / "docs" / "examples"
    image_dir.mkdir(parents=True, exist_ok=True)
    example_dir.mkdir(parents=True, exist_ok=True)

    demos: list[dict[str, Any]] = []
    for case in CASES:
        demos.append(build_case(case, image_dir))

    payload = {
        "version": 1,
        "note": "Deterministic rule-agent demo gallery. No LLM calls or secrets are used.",
        "demos": demos,
    }
    (example_dir / "demo-gallery.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "docs" / "demo-gallery.md").write_text(render_markdown(demos), encoding="utf-8")
    print(f"Wrote {len(demos)} demo cases")


def build_case(case: DemoCase, image_dir: Path) -> dict[str, Any]:
    config = get_preset(
        case.preset,
        {
            "agent_mode": "rule",
            "llm_token_budget": 0,
            "max_llm_calls_per_tick": 0,
        },
    )
    world = ContextGenomeWorld(config, seed=case.seed)
    frames = [render_frame(world.snapshot(), case.preset, case.seed, case.width)]
    for tick in range(1, case.ticks + 1):
        world.step(1)
        if tick % case.sample_every == 0 or tick == case.ticks:
            frames.append(render_frame(world.snapshot(), case.preset, case.seed, case.width))

    gif_path = image_dir / f"demo-{case.slug}.gif"
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=95,
        loop=0,
        optimize=True,
    )

    snapshot = world.full_snapshot()
    lineages = world.lineage_snapshot(limit=3)
    strongest = lineages[0] if lineages else {}
    representative = representative_org(snapshot, strongest.get("lineage_id"))
    skill = representative_skill(representative)
    abilities = rule_agent.parse_abilities(skill)
    strategy = rule_agent.infer_strategy(skill)
    stats = snapshot["stats"]
    return {
        "slug": case.slug,
        "title": case.title,
        "title_zh": case.title_zh,
        "preset": case.preset,
        "seed": case.seed,
        "ticks": case.ticks,
        "sample_every": case.sample_every,
        "gif": f"docs/images/demo-{case.slug}.gif",
        "thesis": case.thesis,
        "thesis_zh": case.thesis_zh,
        "stats": {
            "population": stats.get("population", 0),
            "corpses": stats.get("corpses", 0),
            "lineages": stats.get("lineages", 0),
            "births": stats.get("births", 0),
            "deaths": stats.get("deaths", 0),
            "diversity": round(float(stats.get("diversity") or 0), 3),
            "avg_integrity": round(float(stats.get("avg_integrity") or 0), 3),
        },
        "strongest_lineage": strongest,
        "representative": {
            "org_id": representative.get("org_id", ""),
            "strategy": strategy,
            "generation": representative.get("generation", 0),
            "energy": round(float(representative.get("energy") or 0), 1),
            "integrity": round(float(representative.get("integrity") or 0), 3),
            "abilities": {key: round(value, 2) for key, value in sorted(abilities.items())},
            "context_excerpt": context_excerpt(skill),
        },
    }


def representative_org(snapshot: dict[str, Any], lineage_id: str | None) -> dict[str, Any]:
    organisms = [org for org in snapshot.get("organisms", []) if org.get("alive")]
    if lineage_id:
        organisms = [org for org in organisms if org.get("lineage_id") == lineage_id]
    if not organisms:
        return {}
    return max(
        organisms,
        key=lambda org: (
            float(org.get("energy") or 0),
            float(org.get("integrity") or 0),
            int(org.get("generation") or 0),
        ),
    )


def representative_skill(org: dict[str, Any]) -> str:
    files = org.get("files") or {}
    skill = files.get("SKILL.md") or {}
    return str(skill.get("content") or "")


def context_excerpt(skill: str) -> list[str]:
    lines = []
    for raw_line in skill.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
        if len(lines) >= 7:
            break
    return lines


def render_markdown(demos: list[dict[str, Any]]) -> str:
    lines = [
        "# Context Genome Demo Gallery",
        "",
        "English | 中文",
        "",
        "This gallery is a small set of deterministic, no-token demonstrations. Each case uses the same base rule-agent engine as the browser observer, with a fixed preset and seed. The goal is to show the project idea quickly: context genomes induce behavior, the ecology supplies selection pressure, and the surviving lineages reveal which constraints fit the current world.",
        "",
        "这个 gallery 是一组确定性的零 token 演示。每个案例使用浏览器观察器里的同一个 rule-agent 引擎，只固定 preset 和 seed。它的目的不是替代 LLM 实验，而是让读者快速看懂项目直觉：context genome 诱导行为，生态施加选择压力，幸存谱系显示哪些约束适合当前环境。",
        "",
        "Regenerate everything with:",
        "",
        "```bash",
        "python -m pip install -e \".[docs]\"",
        "python -B scripts/build_demo_gallery.py",
        "```",
        "",
        "Generated metadata is stored in `docs/examples/demo-gallery.json`.",
        "",
    ]
    for demo in demos:
        lines.extend(render_demo(demo))
    return "\n".join(lines).rstrip() + "\n"


def render_demo(demo: dict[str, Any]) -> list[str]:
    stats = demo["stats"]
    strongest = demo.get("strongest_lineage") or {}
    representative = demo["representative"]
    abilities = representative.get("abilities") or {}
    ability_text = ", ".join(f"{key} {value}" for key, value in abilities.items()) or "none"
    excerpt = "\n".join(f"- {line}" for line in representative.get("context_excerpt") or ["No context excerpt."])
    return [
        f"## {demo['title']} / {demo['title_zh']}",
        "",
        f"<img src=\"images/demo-{demo['slug']}.gif\" alt=\"{demo['title']} Context Genome demo\" width=\"520\" />",
        "",
        f"- Preset/seed: `{demo['preset']}` / `{demo['seed']}`",
        f"- Thesis: {demo['thesis']}",
        f"- 中文：{demo['thesis_zh']}",
        f"- Outcome: {stats['population']} active organisms, {stats['lineages']} lineages, {stats['births']} births, {stats['deaths']} deaths, diversity {stats['diversity']}",
        f"- Strongest lineage: `{strongest.get('lineage_id', '-')}` with strategy `{strongest.get('dominant_strategy', '-')}`, population {strongest.get('population', 0)}, score {float(strongest.get('score') or 0):.1f}",
        f"- Representative context: `{representative.get('strategy', '-')}`, generation {representative.get('generation', 0)}, energy {representative.get('energy', 0)}, integrity {representative.get('integrity', 0)}",
        f"- Ability weights: {ability_text}",
        "",
        "Context excerpt:",
        "",
        excerpt,
        "",
    ]


if __name__ == "__main__":
    main()
