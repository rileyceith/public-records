from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Agency(Base):
    __tablename__ = "agencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    code: Mapped[str] = mapped_column(String(24), unique=True)
    region: Mapped[str] = mapped_column(String(120), default="")
    contact_email: Mapped[str] = mapped_column(String(254), default="")


class RecordType(Base):
    __tablename__ = "record_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    field_schema: Mapped[dict] = mapped_column("schema", JSON, default=dict)
    default_access: Mapped[str] = mapped_column(String(16), default="public")
    fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(16), default="citizen")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    agency_id: Mapped[int | None] = mapped_column(ForeignKey("agencies.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    agency: Mapped[Agency | None] = relationship()


class Record(Base):
    __tablename__ = "records"
    __table_args__ = (
        UniqueConstraint("record_number", name="uq_records_record_number"),
        Index("ix_records_status_access", "status", "access_level"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    record_number: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(180), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    record_type_id: Mapped[int] = mapped_column(ForeignKey("record_types.id"), index=True)
    agency_id: Mapped[int] = mapped_column(ForeignKey("agencies.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    access_level: Mapped[str] = mapped_column(String(16), default="public", index=True)
    date_of_event: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    date_filed: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_published: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_modified: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    language: Mapped[str] = mapped_column(String(16), default="en")
    location_address: Mapped[str] = mapped_column(String(255), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    retention_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    record_type: Mapped[RecordType] = relationship()
    agency: Mapped[Agency] = relationship()
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="record",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    parties: Mapped[list["RecordParty"]] = relationship(
        back_populates="record",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    record_id: Mapped[str] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(100), unique=True)
    content_type: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), default="")
    ocr_text: Mapped[str] = mapped_column(Text, default="")
    is_redacted: Mapped[bool] = mapped_column(Boolean, default=False)
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    record: Mapped[Record] = relationship(back_populates="attachments")


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    party_type: Mapped[str] = mapped_column(String(16), default="person")
    id_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    address: Mapped[str] = mapped_column(String(255), default="")


class RecordParty(Base):
    __tablename__ = "record_parties"
    __table_args__ = (UniqueConstraint("record_id", "party_id", "role", name="uq_record_party_role"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[str] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"), index=True)
    party_id: Mapped[str] = mapped_column(ForeignKey("parties.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    record: Mapped[Record] = relationship(back_populates="parties")
    party: Mapped[Party] = relationship()


class AccessRequest(Base):
    __tablename__ = "access_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    record_id: Mapped[str] = mapped_column(ForeignKey("records.id", ondelete="CASCADE"), index=True)
    request_type: Mapped[str] = mapped_column(String(16), default="view")
    purpose: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    payment_status: Mapped[str] = mapped_column(String(16), default="unpaid")
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    record: Mapped[Record] = relationship()
    decided_by: Mapped[User | None] = relationship(foreign_keys=[decided_by_id])


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    actor_email: Mapped[str] = mapped_column(String(254), default="")
    action: Mapped[str] = mapped_column(String(48), index=True)
    entity_type: Mapped[str] = mapped_column(String(48), index=True)
    entity_id: Mapped[str] = mapped_column(String(80), index=True)
    record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User] = relationship()
