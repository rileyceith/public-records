import logging
import uuid
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.access import FULL_ACCESS_ROLES, can_edit, has_full_access, is_visible
from app.core.audit import add_audit_event
from app.core.search import NearFilter, search_records, suggest
from app.core.security import hash_party_id
from app.database import get_db
from app.dependencies import AdminUser, ClientIP, OptionalCurrentUser, RecordWriter
from app.models import Agency, Party, Record, RecordParty, RecordType, User
from app.schemas import (
    AccessLevel,
    PartyInput,
    RecordInput,
    RecordList,
    RecordRead,
    RecordStatus,
    RedactRequest,
    SuggestResponse,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/records", tags=["Records"])
Database = Annotated[Session, Depends(get_db)]

REDACTED = "[REDACTED]"
PUBLISHED = ("published", "redacted")
TRACKED_FIELDS = (
    "record_number",
    "title",
    "summary",
    "record_type_id",
    "agency_id",
    "access_level",
    "date_of_event",
    "date_filed",
    "language",
    "location_address",
    "latitude",
    "longitude",
    "tags",
    "retention_until",
)


def serialize(db: Session, record: Record, user: User | None) -> RecordRead:
    read = RecordRead.model_validate(record)
    read.can_edit = can_edit(user, record)
    read.can_access = has_full_access(db, record, user)
    if not read.can_access:
        read.summary = ""
        read.attachments = []
        read.parties = []
    elif not (user and (user.role in FULL_ACCESS_ROLES or read.can_edit)):
        read.attachments = [attachment for attachment in read.attachments if not attachment.is_redacted]
    return read


def load_record(db: Session, record_id: str) -> Record | None:
    return db.scalar(
        select(Record)
        .options(
            selectinload(Record.attachments),
            selectinload(Record.parties).selectinload(RecordParty.party),
        )
        .where(Record.id == record_id)
        .execution_options(populate_existing=True)
    )


def editable_record(db: Session, record_id: str, user: User) -> Record:
    record = load_record(db, record_id)
    if not record or not is_visible(db, record, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")
    if not can_edit(user, record):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only change records held by your agency.")
    return record


def _resolve_references(db: Session, payload: RecordInput) -> RecordType:
    record_type = db.get(RecordType, payload.record_type_id)
    if not record_type:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose a valid record type.")
    if not db.get(Agency, payload.agency_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose a valid agency.")
    return record_type


def _require_own_agency(user: User, agency_id: int) -> None:
    if user.role == "clerk" and user.agency_id != agency_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Clerks can only manage records for their own agency.")


def _conflict(error: IntegrityError) -> HTTPException:
    logger.info("Record write conflicted with an existing record number: %s", error)
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That record number is already in use.")


@router.get("", response_model=RecordList)
def list_records(
    db: Database,
    q: Annotated[str | None, Query(max_length=120, description="Keyword across title, number, tags, summary and OCR text.")] = None,
    record_type_id: Annotated[int | None, Query(ge=1)] = None,
    agency_id: Annotated[int | None, Query(ge=1)] = None,
    status_filter: Annotated[RecordStatus | None, Query(alias="status")] = None,
    access_level: Annotated[AccessLevel | None, Query()] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    tag: Annotated[str | None, Query(max_length=40)] = None,
    near_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    near_lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    radius_km: Annotated[float, Query(gt=0, le=500)] = 10,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: OptionalCurrentUser = None,
) -> RecordList:
    if (near_lat is None) != (near_lng is None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provide both near_lat and near_lng.")
    near = NearFilter(near_lat, near_lng, radius_km) if near_lat is not None and near_lng is not None else None
    records, total = search_records(
        db,
        user,
        near=near,
        limit=limit,
        offset=offset,
        q=q,
        record_type_id=record_type_id,
        agency_id=agency_id,
        status=status_filter,
        access_level=access_level,
        date_from=date_from,
        date_to=date_to,
        tag=tag,
    )
    return RecordList(items=[serialize(db, record, user) for record in records], total=total, limit=limit, offset=offset)


@router.get("/suggest", response_model=SuggestResponse)
def suggest_records(
    db: Database,
    prefix: Annotated[str, Query(min_length=2, max_length=60)],
    user: OptionalCurrentUser = None,
) -> SuggestResponse:
    return SuggestResponse(suggestions=suggest(db, user, prefix))


@router.get("/{record_id}", response_model=RecordRead)
def get_record(record_id: str, db: Database, ip: ClientIP, user: OptionalCurrentUser = None) -> RecordRead:
    record = load_record(db, record_id)
    if not record or not is_visible(db, record, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")
    read = serialize(db, record, user)
    if user or record.access_level != "public":
        add_audit_event(db, user, "view", "record", record.id, {"record_number": record.record_number}, record_id=record.id, ip=ip)
        db.commit()
    return read


@router.post("", response_model=RecordRead, status_code=status.HTTP_201_CREATED)
def create_record(payload: RecordInput, writer: RecordWriter, db: Database, ip: ClientIP) -> RecordRead:
    record_type = _resolve_references(db, payload)
    _require_own_agency(writer, payload.agency_id)
    values = payload.model_dump()
    values["access_level"] = payload.access_level or record_type.default_access
    values["date_filed"] = payload.date_filed or date.today()
    record = Record(id=str(uuid.uuid4()), status="draft", version=1, created_by_id=writer.id, **values)
    db.add(record)
    try:
        db.flush()
        add_audit_event(
            db,
            writer,
            "create",
            "record",
            record.id,
            {"record_number": record.record_number, "title": record.title},
            record_id=record.id,
            ip=ip,
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise _conflict(error) from error
    return serialize(db, load_record(db, record.id), writer)


@router.put("/{record_id}", response_model=RecordRead)
def update_record(record_id: str, payload: RecordInput, writer: RecordWriter, db: Database, ip: ClientIP) -> RecordRead:
    record = editable_record(db, record_id, writer)
    record_type = _resolve_references(db, payload)
    _require_own_agency(writer, payload.agency_id)
    values = payload.model_dump()
    values["access_level"] = payload.access_level or record_type.default_access
    changes = {}
    for field in TRACKED_FIELDS:
        old, new = getattr(record, field), values[field]
        if old != new:
            changes[field] = [str(old) if old is not None else None, str(new) if new is not None else None]
            setattr(record, field, new)
    if changes:
        action = "edit"
        if record.status in PUBLISHED:
            record.version += 1
            changes["version"] = [str(record.version - 1), str(record.version)]
            action = "new_version"
        add_audit_event(
            db,
            writer,
            action,
            "record",
            record.id,
            {"record_number": record.record_number, "changes": changes},
            record_id=record.id,
            ip=ip,
        )
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise _conflict(error) from error
    return serialize(db, load_record(db, record.id), writer)


def _transition(db: Session, record: Record, writer: User, ip: str, new_status: str, allowed_from: tuple[str, ...]) -> RecordRead:
    if record.status not in allowed_from:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A {record.status} record cannot become {new_status}.",
        )
    previous = record.status
    record.status = new_status
    if new_status == "published" and record.date_published is None:
        record.date_published = datetime.now(timezone.utc)
    add_audit_event(
        db,
        writer,
        {"published": "publish", "archived": "archive", "pending": "submit"}[new_status],
        "record",
        record.id,
        {"record_number": record.record_number, "from_status": previous, "to_status": new_status},
        record_id=record.id,
        ip=ip,
    )
    db.commit()
    return serialize(db, load_record(db, record.id), writer)


@router.post("/{record_id}/submit", response_model=RecordRead, summary="Submit a draft for review")
def submit_record(record_id: str, writer: RecordWriter, db: Database, ip: ClientIP) -> RecordRead:
    return _transition(db, editable_record(db, record_id, writer), writer, ip, "pending", ("draft",))


@router.post("/{record_id}/publish", response_model=RecordRead)
def publish_record(record_id: str, writer: RecordWriter, db: Database, ip: ClientIP) -> RecordRead:
    return _transition(db, editable_record(db, record_id, writer), writer, ip, "published", ("draft", "pending", "archived"))


@router.post("/{record_id}/archive", response_model=RecordRead)
def archive_record(record_id: str, writer: RecordWriter, db: Database, ip: ClientIP) -> RecordRead:
    return _transition(
        db, editable_record(db, record_id, writer), writer, ip, "archived", ("draft", "pending", "published", "redacted")
    )


@router.post("/{record_id}/redact", response_model=RecordRead)
def redact_record(record_id: str, payload: RedactRequest, writer: RecordWriter, db: Database, ip: ClientIP) -> RecordRead:
    record = editable_record(db, record_id, writer)
    if record.status == "archived":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Restore an archived record before redacting it.")
    if "summary" in payload.fields:
        record.summary = REDACTED
    if "location_address" in payload.fields:
        record.location_address = REDACTED
        record.latitude = None
        record.longitude = None
    if "parties" in payload.fields:
        for link in list(record.parties):
            db.delete(link)
    known = {attachment.id: attachment for attachment in record.attachments}
    unknown = [attachment_id for attachment_id in payload.attachment_ids if attachment_id not in known]
    if unknown:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="An attachment does not belong to this record.")
    for attachment_id in payload.attachment_ids:
        known[attachment_id].is_redacted = True
        known[attachment_id].ocr_text = ""
    previous = record.status
    record.status = "redacted" if previous in PUBLISHED else previous
    if previous in PUBLISHED:
        record.version += 1
    add_audit_event(
        db,
        writer,
        "redact",
        "record",
        record.id,
        {"fields": payload.fields, "attachment_ids": payload.attachment_ids, "version": record.version},
        record_id=record.id,
        ip=ip,
    )
    db.commit()
    return serialize(db, load_record(db, record.id), writer)


@router.post("/{record_id}/parties", response_model=RecordRead, status_code=status.HTTP_201_CREATED)
def add_party(record_id: str, payload: PartyInput, writer: RecordWriter, db: Database, ip: ClientIP) -> RecordRead:
    record = editable_record(db, record_id, writer)
    id_hash = hash_party_id(payload.id_number) if payload.id_number and payload.id_number.strip() else ""
    party = None
    if id_hash:
        party = db.scalar(select(Party).where(Party.id_hash == id_hash))
    if party is None:
        party = Party(
            id=str(uuid.uuid4()),
            full_name=payload.full_name,
            party_type=payload.party_type,
            id_hash=id_hash,
            address=payload.address.strip(),
        )
        db.add(party)
        db.flush()
    if any(link.party_id == party.id and link.role == payload.role for link in record.parties):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That party already has this role on the record.")
    db.add(RecordParty(record_id=record.id, party_id=party.id, role=payload.role))
    add_audit_event(
        db,
        writer,
        "add_party",
        "record",
        record.id,
        {"party_id": party.id, "role": payload.role},
        record_id=record.id,
        ip=ip,
    )
    db.commit()
    return serialize(db, load_record(db, record.id), writer)


@router.delete("/{record_id}/parties/{link_id}", response_model=RecordRead)
def remove_party(record_id: str, link_id: int, writer: RecordWriter, db: Database, ip: ClientIP) -> RecordRead:
    record = editable_record(db, record_id, writer)
    link = next((item for item in record.parties if item.id == link_id), None)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Party not found on this record.")
    db.delete(link)
    add_audit_event(
        db, writer, "remove_party", "record", record.id, {"party_id": link.party_id, "role": link.role}, record_id=record.id, ip=ip
    )
    db.commit()
    return serialize(db, load_record(db, record.id), writer)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(record_id: str, admin: AdminUser, db: Database, ip: ClientIP) -> None:
    record = load_record(db, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")
    attachment_names = [attachment.stored_name for attachment in record.attachments]
    details = {"record_number": record.record_number, "title": record.title}
    db.delete(record)
    add_audit_event(db, admin, "delete", "record", record_id, details, record_id=record_id, ip=ip)
    db.commit()

    from app.core.config import UPLOAD_DIR

    for stored_name in attachment_names:
        try:
            (UPLOAD_DIR / stored_name).unlink(missing_ok=True)
        except OSError:
            logger.exception("Unable to remove an attachment for deleted record %s", record_id)
