"""
DTAP Engine — Document Type Assessment Profile
Defines which assessment levels run for each document type,
and configures the neuro-symbolic pipeline.
"""
from app.dtap.registry import DTAPRegistry
from app.dtap.profile import DTAPProfile

__all__ = ["DTAPRegistry", "DTAPProfile"]
