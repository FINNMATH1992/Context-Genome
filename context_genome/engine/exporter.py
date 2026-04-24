from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .world import ContextGenomeWorld


def save_run(world: ContextGenomeWorld, output_root: Path) -> Dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = _run_id(world)
    run_dir = _unique_run_dir(output_root, run_id)
    run_dir.mkdir(parents=True, exist_ok=False)

    final_world = world.full_snapshot()
    events_path = run_dir / "events.jsonl"
    history_path = run_dir / "history.csv"
    lineage_path = run_dir / "lineage.csv"
    final_path = run_dir / "final_world.json"
    summary_path = run_dir / "summary.json"

    with events_path.open("w", encoding="utf-8") as fh:
        for event in final_world["events"]:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")

    _write_csv(history_path, final_world["history"])
    _write_csv(lineage_path, final_world["lineage_history"])

    with final_path.open("w", encoding="utf-8") as fh:
        json.dump(final_world, fh, ensure_ascii=False, indent=2)

    summary = {
        "run_id": run_dir.name,
        "preset": world.config.name,
        "seed": world.seed,
        "tick": world.tick,
        "stats": world.stats(),
        "lineages": world.lineage_snapshot(limit=20),
        "files": {
            "events": _relative_export_path(output_root, events_path),
            "history": _relative_export_path(output_root, history_path),
            "lineage": _relative_export_path(output_root, lineage_path),
            "final_world": _relative_export_path(output_root, final_path),
            "summary": _relative_export_path(output_root, summary_path),
        },
    }
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)

    return summary


def list_runs(output_root: Path) -> List[Dict[str, Any]]:
    if not output_root.exists():
        return []
    rows = []
    for run_dir in sorted(output_root.iterdir(), key=lambda path: path.name, reverse=True):
        if not run_dir.is_dir():
            continue
        summary_path = run_dir / "summary.json"
        if not summary_path.exists():
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        rows.append(
            {
                "run_id": run_dir.name,
                "preset": summary.get("preset"),
                "seed": summary.get("seed"),
                "tick": summary.get("tick"),
                "stats": summary.get("stats", {}),
            }
        )
    return rows


def load_run(output_root: Path, run_id: str) -> ContextGenomeWorld:
    safe_id = Path(run_id).name
    final_path = output_root / safe_id / "final_world.json"
    payload = json.loads(final_path.read_text(encoding="utf-8"))
    return ContextGenomeWorld.from_snapshot(payload)


def _run_id(world: ContextGenomeWorld) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    seed = "none" if world.seed is None else str(world.seed)
    return f"run_{stamp}_{world.config.name}_seed{seed}_t{world.tick}"


def _unique_run_dir(output_root: Path, run_id: str) -> Path:
    run_dir = output_root / run_id
    suffix = 1
    while run_dir.exists():
        run_dir = output_root / f"{run_id}_{suffix}"
        suffix += 1
    return run_dir


def _relative_export_path(output_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(output_root.parent))
    except ValueError:
        return path.name


def _write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
