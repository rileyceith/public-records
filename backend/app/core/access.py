from sqlalchemy import and_, false, or_, select, true
from sqlalchemy.orm import Session

from app.models import AccessRequest, Record, User


PUBLISHED_STATUSES = ("published", "redacted")
FULL_ACCESS_ROLES = ("admin", "auditor")


def approved_record_ids(db: Session, user: User | None):
    """Records a user was explicitly granted (certified copies must also be paid for)."""
    if not user:
        return select(AccessRequest.record_id).where(false())
    return select(AccessRequest.record_id).where(
        AccessRequest.requester_id == user.id,
        AccessRequest.status == "approved",
        or_(
            AccessRequest.request_type == "view",
            AccessRequest.payment_status == "paid",
            AccessRequest.fee_amount == 0,
        ),
    )


def listing_filter(db: Session, user: User | None, levels: tuple[str, ...] = ("public", "restricted")):
    """SQL condition for records a user may see; levels=("public",) gives the full-content condition."""
    if user and user.role in FULL_ACCESS_ROLES:
        return true()
    conditions = [
        and_(Record.status.in_(PUBLISHED_STATUSES), Record.access_level.in_(levels)),
    ]
    if user:
        conditions.append(Record.id.in_(approved_record_ids(db, user)))
        if user.role == "clerk" and user.agency_id:
            conditions.append(Record.agency_id == user.agency_id)
    return or_(*conditions)


def is_visible(db: Session, record: Record, user: User | None) -> bool:
    return bool(db.scalar(select(Record.id).where(Record.id == record.id, listing_filter(db, user))))


def can_edit(user: User | None, record: Record) -> bool:
    if not user:
        return False
    if user.role == "admin":
        return True
    return user.role == "clerk" and user.agency_id is not None and user.agency_id == record.agency_id


def has_full_access(db: Session, record: Record, user: User | None) -> bool:
    """Whether the summary, parties and attachments may be shown."""
    if user and user.role in FULL_ACCESS_ROLES:
        return True
    if can_edit(user, record):
        return True
    if record.status in PUBLISHED_STATUSES and record.access_level == "public":
        return True
    if user and db.scalar(select(Record.id).where(Record.id == record.id, Record.id.in_(approved_record_ids(db, user)))):
        return True
    return False
