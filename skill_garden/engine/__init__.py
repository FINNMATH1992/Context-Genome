"""Compatibility exports for the Context Genome engine."""

from context_genome.engine import ContextGenomeWorld, PRESETS, get_preset

SkillGardenWorld = ContextGenomeWorld

__all__ = ["ContextGenomeWorld", "PRESETS", "SkillGardenWorld", "get_preset"]
