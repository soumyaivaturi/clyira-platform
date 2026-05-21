"""
DTAP Profile — Configuration for how a specific document type gets assessed.
Each profile defines:
- Which levels (L1-L11) are applicable
- Which checks are rule-based vs LLM-based
- Section expectations
- Scoring weights per level
- Sector-specific overlays
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LevelConfig:
    """Configuration for a single assessment level"""
    enabled: bool = True
    engine: str = "rule"  # "rule", "llm", "hybrid"
    weight: float = 1.0
    checks: list[str] = field(default_factory=list)
    required_context: list[str] = field(default_factory=list)  # What data is needed


@dataclass
class DTAPProfile:
    """
    Document Type Assessment Profile.
    Defines the full assessment configuration for a document category.
    """
    dtap_id: str  # e.g. "DTAP-001"
    document_category: str  # e.g. "SOP"
    display_name: str
    version: str = "1.0"

    # Expected document structure
    required_sections: list[str] = field(default_factory=list)
    optional_sections: list[str] = field(default_factory=list)
    section_order_matters: bool = True

    # Assessment level configurations
    levels: dict[str, LevelConfig] = field(default_factory=dict)

    # Scoring
    score_weights: dict[str, float] = field(default_factory=dict)
    passing_threshold: float = 70.0

    # Sector overlays
    sector_overlays: dict[str, dict] = field(default_factory=dict)

    # Document-specific rules
    custom_rules: list[dict] = field(default_factory=list)

    def get_enabled_levels(self) -> list[str]:
        """Return list of enabled level codes"""
        return [code for code, config in self.levels.items() if config.enabled]

    def get_rule_levels(self) -> list[str]:
        """Levels handled by rule engine"""
        return [code for code, config in self.levels.items()
                if config.enabled and config.engine in ("rule", "hybrid")]

    def get_llm_levels(self) -> list[str]:
        """Levels handled by LLM"""
        return [code for code, config in self.levels.items()
                if config.enabled and config.engine in ("llm", "hybrid")]

    def get_level_weight(self, level_code: str) -> float:
        """Get scoring weight for a level"""
        return self.score_weights.get(level_code, 1.0)
