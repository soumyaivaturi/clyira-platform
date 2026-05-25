"""API Key model — for external system integrations (MES, LIMS, VLMS, QMS, ERP)"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class APIKey(Base, TimestampMixin):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    key_prefix = Column(String(16), nullable=False)   # e.g. "clyr_a1b2c3d4" shown in lists
    key_hash = Column(String(255), nullable=False)    # bcrypt hash of the full key
    integration_type = Column(String(50), nullable=True)  # mes, lims, vlms, qms, erp, custom
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    company = relationship("Company", backref="api_keys")
    user = relationship("User", backref="api_keys")
