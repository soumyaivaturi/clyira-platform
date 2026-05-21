"""
DTAP Registry — Holds all registered DTAPs and resolves which profile applies.
V1 ships with: DTAP-001 (SOP), DTAP-002 (CAPA), DTAP-003 (ATM)
"""
from app.dtap.profile import DTAPProfile, LevelConfig
from app.dtap.profiles.sop import SOP_DTAP
from app.dtap.profiles.capa import CAPA_DTAP
from app.dtap.profiles.atm import ATM_DTAP


class DTAPRegistry:
    """Registry of all Document Type Assessment Profiles"""

    _profiles: dict[str, DTAPProfile] = {}

    @classmethod
    def initialize(cls):
        """Load all built-in DTAPs"""
        cls.register(SOP_DTAP)
        cls.register(CAPA_DTAP)
        cls.register(ATM_DTAP)

    @classmethod
    def register(cls, profile: DTAPProfile):
        """Register a DTAP profile"""
        cls._profiles[profile.dtap_id] = profile

    @classmethod
    def get(cls, dtap_id: str) -> DTAPProfile | None:
        """Get a DTAP profile by ID"""
        return cls._profiles.get(dtap_id)

    @classmethod
    def get_by_category(cls, document_category: str) -> DTAPProfile | None:
        """Look up DTAP by document category"""
        for profile in cls._profiles.values():
            if profile.document_category.lower() == document_category.lower():
                return profile
        return None

    @classmethod
    def list_all(cls) -> list[DTAPProfile]:
        """List all registered profiles"""
        return list(cls._profiles.values())

    @classmethod
    def resolve(cls, document_category: str, sub_sector: str | None = None) -> DTAPProfile | None:
        """
        Resolve the appropriate DTAP for a document.
        If sector overlay exists, applies it to the base profile.
        """
        profile = cls.get_by_category(document_category)
        if not profile:
            return None

        # Apply sector overlay if available
        if sub_sector and sub_sector in profile.sector_overlays:
            # In future: clone profile and apply overlay modifications
            pass

        return profile
