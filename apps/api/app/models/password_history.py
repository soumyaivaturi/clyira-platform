"""Password history — prevents reuse of last 5 passwords (21 CFR Part 11 §11.300)"""
from sqlalchemy import Column, String, ForeignKey

from app.models.base import Base, TimestampMixin, generate_uuid


class PasswordHistory(Base, TimestampMixin):
    __tablename__ = "password_history"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
