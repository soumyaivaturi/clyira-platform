"""InspectionMessage — real-time backroom chat model"""
from sqlalchemy import Column, String, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import Base, TimestampMixin, generate_uuid


class InspectionMessage(Base, TimestampMixin):
    __tablename__ = "inspection_messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    inspection_id = Column(String, ForeignKey("inspections.id"), nullable=False)

    # Sender
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    sender_name = Column(String(255), nullable=False)   # denormalized

    # Content
    content = Column(Text, nullable=False)

    # Routing
    room = Column(String(50), default="all")           # all | front | back | prep
    message_type = Column(String(50), default="general")  # general | sme_call | clarification | urgent

    # Links
    linked_request_id = Column(String, ForeignKey("inspection_requests.id"), nullable=True)
    linked_commitment_id = Column(String, nullable=True)

    # Safety
    is_internal = Column(Boolean, default=True)        # always True — inspectors never see this
    converted_to_request_id = Column(String, nullable=True)  # set if this msg became a request

    # Reactions (optional, stored as {emoji: count})
    reactions = Column(JSONB, default=dict)
