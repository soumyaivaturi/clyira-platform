"""Inspector profile — who is in your facility and their known focus areas."""
from sqlalchemy import Column, ForeignKey, String, Text

from app.models.base import Base, TimestampMixin, generate_uuid
from sqlalchemy.dialects.postgresql import JSONB


class InspectionInspector(Base, TimestampMixin):
    __tablename__ = "inspection_inspectors"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    fda_district = Column(String(255))
    role = Column(String(50), default="lead")     # lead | secondary | observer
    focus_areas = Column(JSONB, default=list)      # known areas of interest
    email = Column(String(255))
    notes = Column(Text)
