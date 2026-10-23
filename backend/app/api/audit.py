from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import AuditReader
from app.models import AuditEvent
from app.schemas import AuditEventList


router = APIRouter(prefix="/audit", tags=["Audit history"])
Database = Annotated[Session, Depends(get_db)]


@router.get("", response_model=AuditEventList)
def list_audit_events(
    _reader: AuditReader,
    db: Database,
    q: Annotated[str | None, Query(max_length=120)] = None,
    record_id: Annotated[str | None, Query(max_length=36)] = None,
    action: Annotated[str | None, Query(max_length=48)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditEventList:
    statement = select(AuditEvent)
    if record_id:
        statement = statement.where(AuditEvent.record_id == record_id)
    if action:
        statement = statement.where(AuditEvent.action == action)
    if q:
        search = f"%{q.strip()}%"
        statement = statement.where(
            or_(
                AuditEvent.action.ilike(search),
                AuditEvent.entity_type.ilike(search),
                AuditEvent.entity_id.ilike(search),
                AuditEvent.actor_email.ilike(search),
                AuditEvent.ip_address.ilike(search),
            )
        )
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    events = db.scalars(
        statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return AuditEventList(items=events, total=total, limit=limit, offset=offset)
