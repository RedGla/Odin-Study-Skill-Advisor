import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
import enum
from database import Base

class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"

class MessageStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default=UserRole.USER.value)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    email_verified = Column(Boolean, nullable=False, default=False, server_default="false")
    google_subject = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversations = relationship("Conversation", back_populates="user")
    usage_counters = relationship("UsageCounter", back_populates="user")

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, default="New Conversation")
    persona_id = Column(String, nullable=False, default="odin", server_default="odin")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    sender = Column(String, nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Turn-completion tracking (targets the "≥99% completed-turns-persisted" KPI):
    # assistant rows are written as "pending" before the LLM call, then
    # updated to "completed" or "error" after. User rows are always "completed".
    status = Column(String, default=MessageStatus.COMPLETED.value, nullable=False)

    # Token/cost tracking — populated on assistant messages after a completed LLM call.
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    est_cost = Column(Float, default=0.0)

    conversation = relationship("Conversation", back_populates="messages")

class UsageCounter(Base):
    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("user_id", "date_str", name="uq_usage_counters_user_day"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    date_str = Column(String, nullable=False)  # e.g. "2026-09-14" — one row per user per day

    messages_today = Column(Integer, default=0)
    tokens_today = Column(Integer, default=0)
    reserved_tokens_today = Column(Integer, default=0, nullable=False)
    est_spend_today = Column(Float, default=0.0)

    user = relationship("User", back_populates="usage_counters")

class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    event = Column(String, nullable=False, index=True)
    status = Column(String, nullable=True)
    user_input = Column(String, nullable=True)
    assistant_response = Column(String, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

class AppConfig(Base):
    __tablename__ = "app_config"
    id = Column(Integer, primary_key=True, default=1)
    daily_message_cap = Column(Integer, nullable=False)
    daily_token_cap = Column(Integer, nullable=False)
    rate_limit_requests = Column(Integer, nullable=False)
    rate_limit_window_seconds = Column(Integer, nullable=False)
    registration_enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    chat_enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

class Session(Base):
    __tablename__ = "sessions"
    token_hash = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)


class AuthToken(Base):
    __tablename__ = "auth_tokens"
    token_hash = Column(String, primary_key=True)
    purpose = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    payload = Column(JSON, nullable=False, default=dict)
    expires_at = Column(DateTime, nullable=False, index=True)


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    key = Column(String, primary_key=True)
    attempts = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
