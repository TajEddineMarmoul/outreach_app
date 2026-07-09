from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from src.platform.db import Base
from src.platform.time import utcnow


def json_type():
    return JSON().with_variant(JSONB(), "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320))

    sender_groups: Mapped[list[SenderGroup]] = relationship(back_populates="user", cascade="all, delete-orphan")
    senders: Mapped[list[Sender]] = relationship(back_populates="user", cascade="all, delete-orphan")
    campaigns: Mapped[list[Campaign]] = relationship(back_populates="user", cascade="all, delete-orphan")


class SenderGroup(Base, TimestampMixin):
    __tablename__ = "sender_groups"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_sender_groups_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)

    user: Mapped[User] = relationship(back_populates="sender_groups")
    senders: Mapped[list[Sender]] = relationship(back_populates="group")
    campaigns: Mapped[list[Campaign]] = relationship(back_populates="selected_sender_group")


class Sender(Base, TimestampMixin):
    __tablename__ = "senders"
    __table_args__ = (
        UniqueConstraint("user_id", "email", name="uq_senders_user_email"),
        Index("ix_senders_user_group_status", "user_id", "group_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("sender_groups.id", ondelete="RESTRICT"), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    daily_cap: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    is_default: Mapped[bool] = mapped_column(Integer, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="connected", index=True, nullable=False)
    encrypted_oauth_credentials: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[list[str]] = mapped_column(MutableList.as_mutable(json_type()), default=list, nullable=False)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    recent_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="senders")
    group: Mapped[SenderGroup] = relationship(back_populates="senders")


class Campaign(Base, TimestampMixin):
    __tablename__ = "campaigns"
    __table_args__ = (Index("ix_campaigns_user_status", "user_id", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    selected_sender_group_id: Mapped[int | None] = mapped_column(ForeignKey("sender_groups.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    subject_template: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_template: Mapped[str] = mapped_column(Text, default="", nullable=False)
    fallback_body_template: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True, nullable=False)
    send_settings: Mapped[dict] = mapped_column(MutableDict.as_mutable(json_type()), default=dict, nullable=False)
    attachment_metadata: Mapped[dict] = mapped_column(MutableDict.as_mutable(json_type()), default=dict, nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="campaigns")
    selected_sender_group: Mapped[SenderGroup | None] = relationship(back_populates="campaigns")


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("user_id", "email_normalized", name="uq_contacts_user_email"),
        Index("ix_contacts_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    custom_fields: Mapped[dict] = mapped_column(MutableDict.as_mutable(json_type()), default=dict, nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), default="csv", nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)


class CampaignRecipient(Base, TimestampMixin):
    __tablename__ = "campaign_recipients"
    __table_args__ = (Index("ix_campaign_recipients_status", "campaign_id", "status"),)

    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True)
    contact_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)


class SendJob(Base, TimestampMixin):
    __tablename__ = "send_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_send_jobs_idempotency_key"),
        Index("ix_send_jobs_due", "status", "scheduled_for"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True, nullable=False)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True, nullable=False)
    sender_id: Mapped[int] = mapped_column(ForeignKey("senders.id", ondelete="RESTRICT"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    batch_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(240), nullable=False)


class SendLog(Base, TimestampMixin):
    __tablename__ = "send_log"
    __table_args__ = (Index("ix_send_log_user_campaign", "user_id", "campaign_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id", ondelete="SET NULL"), index=True)
    recipient_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), index=True)
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("senders.id", ondelete="SET NULL"), index=True)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    sender_email: Mapped[str] = mapped_column(String(320), default="", nullable=False)
    subject: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body_snapshot: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    gmail_message_id: Mapped[str | None] = mapped_column(String(255))
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    timezone: Mapped[str] = mapped_column(String(80), default="UTC", nullable=False)
    defaults: Mapped[dict] = mapped_column(MutableDict.as_mutable(json_type()), default=dict, nullable=False)


class OAuthState(Base):
    __tablename__ = "oauth_states"
    __table_args__ = (Index("ix_oauth_states_expiry", "expires_at"),)

    state: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("sender_groups.id", ondelete="CASCADE"), index=True, nullable=False)
    code_verifier: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
