"""User model"""
from sqlalchemy import Column, String, ForeignKey, Boolean, DateTime, Integer
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), default="author")  # admin, qa_lead, author, reviewer, approver, auditor, sme
    department = Column(String(100))
    department_code = Column(String(10))
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)

    # 21 CFR Part 11 §11.300 — account security controls
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, nullable=True)
    force_password_change = Column(Boolean, default=False, nullable=False)

    # 21 CFR Part 11 §11.10(j) — user accountability acknowledgment
    terms_accepted_at = Column(DateTime, nullable=True)

    # Relationships
    company = relationship("Company", back_populates="users")
