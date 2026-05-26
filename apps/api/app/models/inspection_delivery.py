"""Document delivery receipts — timestamped record of every document given to the inspector."""
from sqlalchemy import Boolean, Column, ForeignKey, String, Text

from app.models.base import Base, TimestampMixin, generate_uuid
from sqlalchemy.dialects.postgresql import JSONB


class InspectionDeliveryLog(Base, TimestampMixin):
    __tablename__ = "inspection_delivery_log"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False, index=True)
    request_id = Column(String, ForeignKey("inspection_requests.id"), nullable=True)

    document_titles = Column(JSONB, default=list)          # list of doc names delivered
    delivered_to = Column(String(255))                      # inspector name
    delivery_method = Column(String(50), default="portal")  # portal | email | physical | shared_drive
    delivered_by = Column(String, ForeignKey("users.id"))
    delivered_at = Column(String(50))                       # ISO datetime string

    acknowledgment_received = Column(Boolean, default=False)
    notes = Column(Text)
