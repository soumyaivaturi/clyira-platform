"""Documents attached to a specific inspector request — tracked individually with status."""
from sqlalchemy import Column, ForeignKey, Integer, String

from app.models.base import Base, TimestampMixin, generate_uuid


class InspectionRequestDocument(Base, TimestampMixin):
    __tablename__ = "inspection_request_documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    request_id = Column(String, ForeignKey("inspection_requests.id"), nullable=False, index=True)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False, index=True)

    filename = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer)
    file_path = Column(String(500))               # storage path / URL
    status = Column(String(20), default="pending")  # pending | ready | delivered
    uploaded_by = Column(String, ForeignKey("users.id"))
