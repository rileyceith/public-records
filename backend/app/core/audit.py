from sqlalchemy.orm import Session

from app.models import AuditEvent, User


def add_audit_event(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict | None = None,
    *,
    record_id: str | None = None,
    ip: str = "",
) -> None:
    db.add(
        AuditEvent(
            actor_id=actor.id if actor else None,
            actor_email=actor.email if actor else "",
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            record_id=record_id,
            ip_address=ip,
            details=details or {},
        )
    )
