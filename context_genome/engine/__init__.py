"""Core engine for the Context Genome artificial life sandbox."""

from .presets import PRESETS, get_preset

__all__ = ["PRESETS", "ContextGenomeWorld", "get_preset"]


def __getattr__(name: str):
    if name == "ContextGenomeWorld":
        from .world import ContextGenomeWorld

        return ContextGenomeWorld
    raise AttributeError(name)
