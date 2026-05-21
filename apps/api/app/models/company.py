"""Company model — multi-tenant root entity"""
from sqlalchemy import Column, String, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    sub_sectors = Column(JSONB, default=list)
    agencies = Column(JSONB, default=list)
    markets = Column(JSONB, default=list)
    certifications = Column(JSONB, default=list)
    settings = Column(JSONB, default=dict)
    onboarding_complete = Column(Boolean, default=False)
    subscription_tier = Column(String(50), default="professional")

    # Relationships
    users = relationship("User", back_populates="company")
    documents = relationship("Document", back_populates="company")
    assessments = relationship("Assessment", back_populates="company")
    readiness_scores = relationship("ReadinessScore", back_populates="company")
    inspections = relationship("Inspection", back_populates="company")
