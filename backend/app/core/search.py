import math
from dataclasses import dataclass
from datetime import date

from sqlalchemy import String, and_, cast, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.access import listing_filter
from app.models import Attachment, Record, User


NEAR_CANDIDATE_LIMIT = 2000


@dataclass(frozen=True)
class NearFilter:
    latitude: float
    longitude: float
    radius_km: float


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_statement(
    db: Session,
    user: User | None,
    *,
    q: str | None = None,
    record_type_id: int | None = None,
    agency_id: int | None = None,
    status: str | None = None,
    access_level: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    tag: str | None = None,
):
    statement = select(Record).options(
        selectinload(Record.attachments),
        selectinload(Record.parties),
    )
    filters = [listing_filter(db, user)]
    if q and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        metadata_match = or_(
            Record.title.ilike(pattern, escape="\\"),
            Record.record_number.ilike(pattern, escape="\\"),
            cast(Record.tags, String).ilike(pattern, escape="\\"),
        )
        # Content (summary and OCR text) is only searchable where the user may read it.
        content_match = and_(
            listing_filter(db, user, levels=("public",)),
            or_(
                Record.summary.ilike(pattern, escape="\\"),
                exists().where(
                    Attachment.record_id == Record.id,
                    Attachment.ocr_text.ilike(pattern, escape="\\"),
                    Attachment.is_redacted.is_(False),
                ),
            ),
        )
        filters.append(or_(metadata_match, content_match))
    if record_type_id:
        filters.append(Record.record_type_id == record_type_id)
    if agency_id:
        filters.append(Record.agency_id == agency_id)
    if status:
        filters.append(Record.status == status)
    if access_level:
        filters.append(Record.access_level == access_level)
    if date_from:
        filters.append(Record.date_of_event >= date_from)
    if date_to:
        filters.append(Record.date_of_event <= date_to)
    if tag and tag.strip():
        filters.append(cast(Record.tags, String).ilike(f'%"{_escape_like(tag.strip().lower())}"%', escape="\\"))
    return statement.where(*filters)


def search_records(
    db: Session,
    user: User | None,
    *,
    near: NearFilter | None = None,
    limit: int = 25,
    offset: int = 0,
    **filters,
) -> tuple[list[Record], int]:
    statement = build_statement(db, user, **filters)
    ordering = (
        Record.date_of_event.is_(None),
        Record.date_of_event.desc(),
        Record.last_modified.desc(),
    )
    if near is None:
        total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
        return list(db.scalars(statement.order_by(*ordering).limit(limit).offset(offset)).all()), total

    lat_delta = near.radius_km / 111.0
    lon_delta = near.radius_km / max(111.0 * math.cos(math.radians(near.latitude)), 0.01)
    candidates = db.scalars(
        statement.where(
            Record.latitude.is_not(None),
            Record.longitude.is_not(None),
            Record.latitude.between(near.latitude - lat_delta, near.latitude + lat_delta),
            Record.longitude.between(near.longitude - lon_delta, near.longitude + lon_delta),
        )
        .order_by(*ordering)
        .limit(NEAR_CANDIDATE_LIMIT)
    ).all()
    ranked = sorted(
        (
            (haversine_km(near.latitude, near.longitude, record.latitude, record.longitude), record)
            for record in candidates
        ),
        key=lambda pair: pair[0],
    )
    within = [record for distance, record in ranked if distance <= near.radius_km]
    return within[offset : offset + limit], len(within)


def suggest(db: Session, user: User | None, prefix: str, limit: int = 8) -> list[str]:
    prefix = prefix.strip()
    if len(prefix) < 2:
        return []
    pattern = f"{_escape_like(prefix)}%"
    word_pattern = f"% {_escape_like(prefix)}%"
    titles = db.scalars(
        select(Record.title)
        .where(
            listing_filter(db, user),
            or_(Record.title.ilike(pattern, escape="\\"), Record.title.ilike(word_pattern, escape="\\")),
        )
        .distinct()
        .order_by(Record.title)
        .limit(limit)
    ).all()
    numbers = db.scalars(
        select(Record.record_number)
        .where(listing_filter(db, user), Record.record_number.ilike(pattern, escape="\\"))
        .order_by(Record.record_number)
        .limit(limit)
    ).all()
    return list(dict.fromkeys([*titles, *numbers]))[:limit]
