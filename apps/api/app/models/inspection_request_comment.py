"""Comments thread on an individual inspector request — internal war-room notes."""
from sqlalchemy import Column, ForeignKey, String, Text

from app.models.base import Base, TimestampMixin, generate_uuid


class InspectionRequestComment(Base, TimestampMixin):
    __tablename__ = "inspection_request_comments"

    id = Column(String, primary_key=True, default=generate_uuid)
    request_id = Column(String, ForeignKey("inspection_requests.id"), nullable=False, index=True)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False)

    author_id = Column(String, ForeignKey("users.id"), nullable=False)
    author_name = Column(String(255))   # denormalized for display speed
    content = Column(Text, nullable=False)
