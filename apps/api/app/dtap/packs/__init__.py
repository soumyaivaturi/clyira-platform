"""
Modular Review Packs — composable DTAP overlays for the Batch & Lot Record Review module.

Each pack defines the checks that apply to a specific sector or manufacturing context.
Packs are additive: Core Production always runs; sector packs layer on top.
"""
from app.dtap.profile import DTAPProfile, LevelConfig
from copy import deepcopy


def compose_packs(*packs: dict) -> dict[str, LevelConfig]:
    """
    Merge multiple pack level-config dicts into a single levels dict.
    For shared levels, checks are concatenated; highest weight wins; most permissive engine wins.
    """
    ENGINE_RANK = {"rule": 0, "hybrid": 1, "llm": 2}
    merged: dict[str, LevelConfig] = {}

    for pack in packs:
        for level, config in pack.items():
            if level not in merged:
                merged[level] = deepcopy(config)
            else:
                existing = merged[level]
                new_checks = [c for c in config.checks if c not in existing.checks]
                existing.checks.extend(new_checks)
                if config.weight > existing.weight:
                    existing.weight = config.weight
                if ENGINE_RANK.get(config.engine, 0) > ENGINE_RANK.get(existing.engine, 0):
                    existing.engine = config.engine
                existing.required_context = list(set(existing.required_context + config.required_context))

    return merged
