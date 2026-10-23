from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import add_audit_event
from app.database import get_db
from app.dependencies import AdminUser, ClientIP
from app.models import Agency, RecordType
from app.schemas import AgencyInput, AgencyRead, RecordTypeInput, RecordTypeRead


router = APIRouter(tags=["Reference data"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/agencies", response_model=list[AgencyRead])
def list_agencies(db: Database) -> list[Agency]:
    return list(db.scalars(select(Agency).order_by(Agency.name)).all())


@router.post("/agencies", response_model=AgencyRead, status_code=status.HTTP_201_CREATED)
def create_agency(payload: AgencyInput, admin: AdminUser, db: Database, ip: ClientIP) -> Agency:
    agency = Agency(**payload.model_dump())
    db.add(agency)
    try:
        db.flush()
        add_audit_event(db, admin, "create", "agency", str(agency.id), {"code": agency.code}, ip=ip)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An agency with that name or code already exists.") from error
    return agency


@router.get("/record-types", response_model=list[RecordTypeRead])
def list_record_types(db: Database) -> list[RecordTypeRead]:
    return [RecordTypeRead.model_validate(item) for item in db.scalars(select(RecordType).order_by(RecordType.name)).all()]


@router.post("/record-types", response_model=RecordTypeRead, status_code=status.HTTP_201_CREATED)
def create_record_type(payload: RecordTypeInput, admin: AdminUser, db: Database, ip: ClientIP) -> RecordTypeRead:
    values = payload.model_dump()
    record_type = RecordType(
        name=values["name"],
        field_schema=values["field_schema"],
        default_access=values["default_access"],
        fee=values["fee"],
    )
    db.add(record_type)
    try:
        db.flush()
        add_audit_event(db, admin, "create", "record_type", str(record_type.id), {"name": record_type.name}, ip=ip)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A record type with that name already exists.") from error
    return RecordTypeRead.model_validate(record_type)
