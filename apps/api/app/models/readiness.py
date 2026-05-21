"""Readiness Score model"""
from sqlalchemy import Column, String, Float, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class ReadinessScore(Base, TimestampMixin):
    __tablename__ = "readiness_scores"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)

    # Scope
    scope = Column(String(50), nullable=False)  # company, department, document
    scope_identifier = Column(String(100))  # department code or document_id

    # Score
    score = Column(Float, nullable=False)
    score_band = Column(String(20))  # Excellent, Good, Moderate, Poor, Critical
    weight = Column(Float, default=1.0)  # Weight in parent aggregation

    # Breakdown
    component_scores = Column(JSONB, default=dict)  # Per-level breakdown
    gap_count = Column(Integer, default=0)
    missing_documents = Column(Integer, default=0)
    expired_documents = Column(Integer, default=0)

    # Trend
    previous_score = Column(Float)
    trend_direction = Column(String(10))  # up, down, stable
    trend_magnitude = Column(Float)

    # Relationships
    company = relationship("Company", back_populates="readiness_scores")
