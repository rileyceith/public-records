import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.access import FULL_ACCESS_ROLES, can_edit, has_full_access, is_visible
from app.core.audit import add_audit_event
from app.database import get_db
from app.dependencies import ClientIP, CurrentUser, RecordWriter
from app.models import AccessRequest, Record, User
from app.schemas import AccessDecision, AccessRequestInput, AccessRequestRead


router = APIRouter(prefix="/access-requests", tags=["Access requests"])
Database = Annotated[Session, Depends(get_db)]


def serialize(item: AccessRequest) -> AccessRequestRead:
    return AccessRequestRead(
        id=item.id,
        record_id=item.record_id,
        record_number=item.record.record_number,
        record_title=item.record.title,
        requester_id=item.requester_id,
        requester_email=item.requester.email,
        request_type=item.request_type,
        purpose=item.purpose,
        status=item.status,
        fee_amount=item.fee_amount,
        payment_status=item.payment_status,
        decided_by_id=item.decided_by_id,
        decision_reason=item.decision_reason,
        requested_at=item.requested_at,
        decided_at=item.decided_at,
    )


def _load(db: Session, request_id: str) -> AccessRequest:
    item = db.scalar(
        select(AccessRequest)
        .options(joinedload(AccessRequest.record), joinedload(AccessRequest.requester))
        .where(AccessRequest.id == request_id)
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
    return item


def _reviewable(item: AccessRequest, user: User) -> AccessRequest:
    if not can_edit(user, item.record):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found.")
    return item


@router.post("", response_model=AccessRequestRead, status_code=status.HTTP_201_CREATED)
def create_request(payload: AccessRequestInput, user: CurrentUser, db: Database, ip: ClientIP) -> AccessRequestRead:
    if user.role != "citizen":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff accounts already have access through their role.")
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your identity must be verified before requesting records.")
    record = db.get(Record, payload.record_id)
    if not record or not is_visible(db, record, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found.")
    if payload.request_type == "view" and has_full_access(db, record, user):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You can already view this record.")
    duplicate = db.scalar(
        select(AccessRequest.id).where(
            AccessRequest.requester_id == user.id,
            AccessRequest.record_id == record.id,
            AccessRequest.request_type == payload.request_type,
            AccessRequest.status.in_(("pending", "approved")),
        )
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You already have an open request for this record.")
    fee = record.record_type.fee if payload.request_type == "certified_copy" else Decimal("0.00")
    item = AccessRequest(
        id=str(uuid.uuid4()),
        requester_id=user.id,
        record_id=record.id,
        request_type=payload.request_type,
        purpose=payload.purpose,
        fee_amount=fee,
        payment_status="paid" if fee == 0 else "unpaid",
    )
    db.add(item)
    db.flush()
    add_audit_event(
        db, user, "request_access", "access_request", item.id, {"request_type": item.request_type}, record_id=record.id, ip=ip
    )
    db.commit()
    return serialize(_load(db, item.id))


@router.get("", response_model=list[AccessRequestRead])
def list_requests(
    user: CurrentUser,
    db: Database,
    status_filter: Annotated[str | None, Query(alias="status", pattern="^(pending|approved|denied)$")] = None,
) -> list[AccessRequestRead]:
    statement = select(AccessRequest).options(joinedload(AccessRequest.record), joinedload(AccessRequest.requester))
    if user.role == "citizen":
        statement = statement.where(AccessRequest.requester_id == user.id)
    elif user.role == "clerk":
        statement = statement.join(Record, Record.id == AccessRequest.record_id).where(Record.agency_id == user.agency_id)
    elif user.role not in FULL_ACCESS_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to do that.")
    if status_filter:
        statement = statement.where(AccessRequest.status == status_filter)
    items = db.scalars(statement.order_by(AccessRequest.requested_at.desc()).limit(200)).unique().all()
    return [serialize(item) for item in items]


def _decide(db: Session, item: AccessRequest, user: User, ip: str, decision: str, reason: str) -> AccessRequestRead:
    _reviewable(item, user)
    if item.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This request has already been decided.")
    if item.requester_id == user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot decide your own request.")
    item.status = decision
    item.decided_by_id = user.id
    item.decision_reason = reason.strip()
    item.decided_at = datetime.now(timezone.utc)
    add_audit_event(
        db,
        user,
        "approve_access" if decision == "approved" else "deny_access",
        "access_request",
        item.id,
        {"reason": item.decision_reason},
        record_id=item.record_id,
        ip=ip,
    )
    db.commit()
    return serialize(_load(db, item.id))


@router.post("/{request_id}/approve", response_model=AccessRequestRead)
def approve_request(
    request_id: str, writer: RecordWriter, db: Database, ip: ClientIP, payload: AccessDecision | None = None
) -> AccessRequestRead:
    return _decide(db, _load(db, request_id), writer, ip, "approved", payload.reason if payload else "")


@router.post("/{request_id}/deny", response_model=AccessRequestRead)
def deny_request(request_id: str, payload: AccessDecision, writer: RecordWriter, db: Database, ip: ClientIP) -> AccessRequestRead:
    if not payload.reason.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Give a reason for denying the request.")
    return _decide(db, _load(db, request_id), writer, ip, "denied", payload.reason)


@router.post("/{request_id}/mark-paid", response_model=AccessRequestRead)
def mark_paid(request_id: str, writer: RecordWriter, db: Database, ip: ClientIP) -> AccessRequestRead:
    """Record an offline or gateway-confirmed payment for a certified copy."""
    item = _reviewable(_load(db, request_id), writer)
    if item.status != "approved" or item.payment_status == "paid":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only approved, unpaid requests can be marked as paid.")
    item.payment_status = "paid"
    add_audit_event(
        db, writer, "payment", "access_request", item.id, {"amount": str(item.fee_amount)}, record_id=item.record_id, ip=ip
    )
    db.commit()
    return serialize(_load(db, item.id))
