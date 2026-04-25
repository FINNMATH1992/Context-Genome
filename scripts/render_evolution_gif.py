from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from context_genome.engine import ContextGenomeWorld, get_preset


PALETTE = ["#168b88", "#c98b22", "#c94f6d", "#5967c7", "#3a965b", "#8f5fbf", "#d46f3d", "#2d7db3"]
TRAIT_INITIALS = {
    "forage": "F",
    "spread": "S",
    "guard": "G",
    "repair": "R",
    "migrate": "M",
    "minimal": "N",
    "scavenge": "V",
    "steal": "T",
}
TRAIT_COLORS = {
    "forage": "#168b88",
    "spread": "#5967c7",
    "guard": "#3a965b",
    "repair": "#c98b22",
    "migrate": "#2d7db3",
    "minimal": "#60707a",
    "scavenge": "#8f5fbf",
    "steal": "#c94f6d",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a compact Context Genome evolution GIF.")
    parser.add_argument("--run-summary", default="", help="Optional runs/<id>/summary.json used for preset and seed defaults.")
    parser.add_argument("--preset", default="", help="Preset name. Defaults to run summary preset or sandbox.")
    parser.add_argument("--seed", default="", help="Random seed. Defaults to run summary seed or 7.")
    parser.add_argument("--ticks", type=int, default=120)
    parser.add_argument("--sample-every", type=int, default=2)
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--output", default="docs/images/context-genome-evolution.gif")
    args = parser.parse_args()

    summary = load_summary(args.run_summary)
    preset = args.preset or str(summary.get("preset") or "sandbox")
    seed = int(args.seed or summary.get("seed") or 7)
    ticks = max(1, args.ticks)
    sample_every = max(1, args.sample_every)
    output = Path(args.output)

    config = get_preset(
        preset,
        {
            "agent_mode": "rule",
            "llm_token_budget": 0,
            "max_llm_calls_per_tick": 0,
        },
    )
    world = ContextGenomeWorld(config, seed=seed)
    frames = [render_frame(world.snapshot(), preset, seed, args.width)]
    for tick in range(1, ticks + 1):
        world.step(1)
        if tick % sample_every == 0 or tick == ticks:
            frames.append(render_frame(world.snapshot(), preset, seed, args.width))

    output.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=95,
        loop=0,
        optimize=True,
    )
    print(f"Wrote {output} ({len(frames)} frames, preset={preset}, seed={seed})")


def load_summary(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {}
    path = Path(path_text)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def render_frame(state: dict[str, Any], preset: str, seed: int, width: int) -> Image.Image:
    margin = 22
    header_h = 74
    footer_h = 50
    grid_gap = 2
    cols = int(state["config"]["width"])
    rows = int(state["config"]["height"])
    grid_px = min(width - margin * 2 - 250, 390)
    cell = max(8, (grid_px - grid_gap * (cols - 1)) // cols)
    grid_w = cell * cols + grid_gap * (cols - 1)
    grid_h = cell * rows + grid_gap * (rows - 1)
    panel_x = margin + grid_w + 22
    height = max(header_h + grid_h + footer_h, 420)

    image = Image.new("RGB", (width, height), "#f5f7f8")
    draw = ImageDraw.Draw(image)
    font = load_font(13)
    small = load_font(10)
    tiny = load_font(8)
    bold = load_font(18)

    draw.text((margin, 18), "Context Genome Evolution", fill="#172026", font=bold)
    draw.text((margin, 44), f"preset {preset} / seed {seed} / tick {state['tick']} / rule-agent sample", fill="#60707a", font=small)

    cells = state["cells"]
    max_energy = max([float(item.get("energy") or 0) for item in cells] + [1.0])
    max_size = max([float(item.get("directory_size") or 0) for item in cells] + [1.0])
    grid_x = margin
    grid_y = header_h
    draw.rounded_rectangle(
        [grid_x - 8, grid_y - 8, grid_x + grid_w + 8, grid_y + grid_h + 8],
        radius=8,
        fill="#10171c",
        outline="#d8e0e5",
    )
    for item in cells:
        x = grid_x + int(item["x"]) * (cell + grid_gap)
        y = grid_y + int(item["y"]) * (cell + grid_gap)
        energy_ratio = min(1.0, max(0.0, float(item.get("energy") or 0) / max_energy))
        size_ratio = min(1.0, max(0.0, float(item.get("directory_size") or 0) / max_size))
        color = blend("#1b262d", "#3f8b70", energy_ratio)
        draw.rounded_rectangle([x, y, x + cell, y + cell], radius=3, fill=color, outline="#31424b")
        if size_ratio > 0.08:
            overlay = blend(color, "#c98b22", size_ratio * 0.35)
            draw.rounded_rectangle([x + 2, y + 2, x + cell - 2, y + cell - 2], radius=2, outline=overlay)
        lineage = item.get("dominant_lineage")
        if lineage:
            draw.rectangle([x, y, x + 3, y + cell], fill=lineage_color(str(lineage)))
        trait = str(item.get("skill_trait") or "")
        if item.get("org_count") or (int(item["x"]) == 0 and int(item["y"]) == 0):
            draw.rounded_rectangle([x + 3, y + 3, x + 15, y + 15], radius=3, fill=TRAIT_COLORS.get(trait, "#60707a"))
            draw.text((x + 6, y + 4), TRAIT_INITIALS.get(trait, ""), fill="#ffffff", font=tiny)
        org_count = int(item.get("org_count") or 0)
        if org_count:
            dot_count = min(org_count, 4)
            for index in range(dot_count):
                dx = x + cell - 7 - (index % 2) * 6
                dy = y + cell - 7 - (index // 2) * 6
                draw.ellipse([dx, dy, dx + 4, dy + 4], fill="#eef5f1")
        corpse_count = int(item.get("corpse_count") or 0)
        if corpse_count:
            draw.rectangle([x + cell - 5, y + 2, x + cell - 2, y + 8], fill="#c94f6d")

    stats = state["stats"]
    lineages = state.get("lineages") or []
    draw_metrics(draw, panel_x, header_h, stats, lineages, font, small)
    draw_history(draw, margin, grid_y + grid_h + 20, width - margin * 2, 24, state.get("history") or [])
    return image


def draw_metrics(draw: ImageDraw.ImageDraw, x: int, y: int, stats: dict[str, Any], lineages: list[dict[str, Any]], font, small) -> None:
    rows = [
        ("active", stats.get("population", 0)),
        ("lineages", stats.get("lineages", 0)),
        ("births", stats.get("births", 0)),
        ("deaths", stats.get("deaths", 0)),
        ("diversity", f"{float(stats.get('diversity') or 0):.2f}"),
        ("integrity", f"{float(stats.get('avg_integrity') or 0) * 100:.0f}%"),
    ]
    draw.rounded_rectangle([x, y, x + 215, y + 210], radius=9, fill="#ffffff", outline="#d8e0e5")
    draw.text((x + 12, y + 12), "Live Signals", fill="#172026", font=font)
    top = y + 38
    for index, (label, value) in enumerate(rows):
        ry = top + index * 24
        draw.text((x + 12, ry), str(value), fill="#172026", font=font)
        draw.text((x + 86, ry + 2), label, fill="#60707a", font=small)
    if lineages:
        leader = lineages[0]
        ly = y + 188
        draw.text((x + 12, ly), f"leader {leader.get('lineage_id', '-')}", fill=lineage_color(str(leader.get("lineage_id", ""))), font=small)


def draw_history(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int, history: list[dict[str, Any]]) -> None:
    draw.rounded_rectangle([x, y, x + width, y + height], radius=6, fill="#ffffff", outline="#d8e0e5")
    if len(history) < 2:
        return
    max_pop = max([float(row.get("population") or 0) for row in history] + [1.0])
    points = []
    for index, row in enumerate(history):
        px = x + 8 + index / max(1, len(history) - 1) * (width - 16)
        py = y + height - 5 - (float(row.get("population") or 0) / max_pop) * (height - 10)
        points.append((px, py))
    if len(points) >= 2:
        draw.line(points, fill="#168b88", width=2)


def lineage_color(value: str) -> str:
    h = 0
    for char in value:
        h = (h * 31 + ord(char)) & 0xFFFFFFFF
    return PALETTE[h % len(PALETTE)]


def blend(a: str, b: str, amount: float) -> str:
    amount = min(1.0, max(0.0, amount))
    ar, ag, ab = hex_to_rgb(a)
    br, bg, bb = hex_to_rgb(b)
    return rgb_to_hex(
        int(ar + (br - ar) * amount),
        int(ag + (bg - ag) * amount),
        int(ab + (bb - ab) * amount),
    )


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def load_font(size: int):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


if __name__ == "__main__":
    main()
