import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid email address.")
        return value


class UserRegister(UserLogin):
    full_name: str = Field(min_length=2, max_length=120)

    @field_validator("password")
    @classmethod
    def enforce_password_policy(cls, value: str) -> str:
        if len(value) < 12:
            raise ValueError("Passwords must contain at least 12 characters.")
        return value

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter a full name.")
        return value


Role = Literal["citizen", "clerk", "admin", "auditor"]


class UserCreate(UserRegister):
    role: Role = "citizen"
    agency_id: int | None = None
    is_verified: bool = False


class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
    is_verified: bool | None = None
    agency_id: int | None = None


class AgencyInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=24)
    region: str = Field(default="", max_length=120)
    contact_email: str = Field(default="", max_length=254)

    @field_validator("name", "code")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class AgencyRead(AgencyInput):
    model_config = ConfigDict(from_attributes=True)

    id: int


AccessLevel = Literal["public", "restricted", "confidential"]
RecordStatus = Literal["draft", "pending", "published", "archived", "redacted"]


class RecordTypeInput(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    field_schema: dict = Field(default_factory=dict)
    default_access: AccessLevel = "public"
    fee: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=10, decimal_places=2)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class RecordTypeRead(RecordTypeInput):
    model_config = ConfigDict(from_attributes=True)

    id: int


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    is_verified: bool
    mfa_enabled: bool
    agency_id: int | None
    created_at: datetime


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserRead


class AttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    original_name: str
    content_type: str
    size_bytes: int
    page_count: int | None = None
    checksum_sha256: str = ""
    is_redacted: bool = False
    created_at: datetime


class PartyInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    party_type: Literal["person", "company", "agency"] = "person"
    id_number: str | None = Field(default=None, max_length=64, description="Hashed on receipt; never stored or returned.")
    address: str = Field(default="", max_length=255)
    role: Literal["owner", "applicant", "witness", "official"]

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Enter a name.")
        return value


class PartyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    party_type: str
    address: str


class RecordPartyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    party: PartyRead


class RecordInput(BaseModel):
    record_number: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=3, max_length=180)
    summary: str = Field(default="", max_length=5000)
    record_type_id: int
    agency_id: int
    access_level: AccessLevel | None = Field(default=None, description="Defaults to the record type's access level.")
    date_of_event: date | None = None
    date_filed: date | None = None
    language: str = Field(default="en", min_length=2, max_length=16)
    location_address: str = Field(default="", max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    tags: list[str] = Field(default_factory=list, max_length=20)
    retention_until: date | None = None

    @field_validator("record_number", "title", "language")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("summary", "location_address")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in value:
            tag = tag.strip().lower()
            if not tag or len(tag) > 40:
                raise ValueError("Tags must be 1 to 40 characters.")
            if tag not in cleaned:
                cleaned.append(tag)
        return cleaned


class RecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    record_number: str
    title: str
    summary: str
    record_type: RecordTypeRead
    agency: AgencyRead
    status: RecordStatus
    access_level: AccessLevel
    date_of_event: date | None
    date_filed: date | None
    date_published: datetime | None
    last_modified: datetime
    created_at: datetime
    version: int
    language: str
    location_address: str
    latitude: float | None
    longitude: float | None
    tags: list[str]
    retention_until: date | None
    attachments: list[AttachmentRead] = Field(default_factory=list)
    parties: list[RecordPartyRead] = Field(default_factory=list)
    can_access: bool = True
    can_edit: bool = False


class RecordList(BaseModel):
    items: list[RecordRead]
    total: int
    limit: int
    offset: int


class RedactRequest(BaseModel):
    fields: list[Literal["summary", "location_address", "parties"]] = Field(min_length=1)
    attachment_ids: list[str] = Field(default_factory=list)


class AccessRequestInput(BaseModel):
    record_id: str
    request_type: Literal["view", "certified_copy"] = "view"
    purpose: str = Field(min_length=5, max_length=2000)

    @field_validator("purpose")
    @classmethod
    def strip_purpose(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 5:
            raise ValueError("Describe why you need this record.")
        return value


class AccessDecision(BaseModel):
    reason: str = Field(default="", max_length=2000)


class AccessRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    record_id: str
    record_number: str
    record_title: str
    requester_id: int
    requester_email: str
    request_type: str
    purpose: str
    status: str
    fee_amount: Decimal
    payment_status: str
    decided_by_id: int | None
    decision_reason: str
    requested_at: datetime
    decided_at: datetime | None


class SuggestResponse(BaseModel):
    suggestions: list[str]


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: int | None
    actor_email: str
    action: str
    entity_type: str
    entity_id: str
    record_id: str | None = None
    ip_address: str = ""
    details: dict
    created_at: datetime


class AuditEventList(BaseModel):
    items: list[AuditEventRead]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "public-records-api"
