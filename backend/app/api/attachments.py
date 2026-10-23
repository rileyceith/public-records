import hashlib
import logging
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.records import editable_record
from app.core.access import FULL_ACCESS_ROLES, can_edit, has_full_access, is_visible
from app.core.audit import add_audit_event
from app.core.config import ALLOWED_ATTACHMENT_TYPES, MAX_ATTACHMENT_BYTES, UPLOAD_DIR
from app.database import get_db
from app.dependencies import ClientIP, OptionalCurrentUser, RecordWriter
from app.models import Attachment, Record, User
from app.schemas import AttachmentRead


logger = logging.getLogger(__name__)
router = APIRouter(tags=["Attachments"])
Database = Annotated[Session, Depends(get_db)]
TEXT_TYPES = {"text/plain", "text/csv"}
MAX_OCR_CHARACTERS = 200_000


def _extract_text(content: bytes, content_type: str) -> str:
    """Plain-text and CSV files are indexed directly; scanned PDFs and images need an OCR engine."""
    if content_type not in TEXT_TYPES:
        return ""
    return content.decode("utf-8", errors="replace")[:MAX_OCR_CHARACTERS]


def _readable_attachment(db: Session, attachment: Attachment, user: User | None) -> Record:
    record = db.get(Record, attachment.record_id)
    if not record or not is_visible(db, record, user) or not has_full_access(db, record, user):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")
    if attachment.is_redacted and not (user and (user.role in FULL_ACCESS_ROLES or can_edit(user, record))):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This attachment has been redacted.")
    return record


@router.post(
    "/records/{record_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    record_id: str,
    writer: RecordWriter,
    db: Database,
    ip: ClientIP,
    file: Annotated[UploadFile, File()],
) -> Attachment:
    record = editable_record(db, record_id, writer)
    original_name = (file.filename or "attachment").replace("\\", "/").rsplit("/", 1)[-1]
    original_name = "".join(character for character in original_name if character.isprintable()).strip()[:255]
    suffix = Path(original_name).suffix.lower()
    content_type = ALLOWED_ATTACHMENT_TYPES.get(suffix)
    if not original_name or not content_type:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Supported files: PDF, PNG, JPG, TXT, and CSV.",
        )

    content = await file.read(MAX_ATTACHMENT_BYTES + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The attachment is empty.")
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Attachments must be 10 MB or smaller.",
        )

    attachment_id = str(uuid.uuid4())
    stored_name = f"{attachment_id}{suffix}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOAD_DIR / stored_name
    try:
        target.write_bytes(content)
        attachment = Attachment(
            id=attachment_id,
            record_id=record.id,
            original_name=original_name,
            stored_name=stored_name,
            content_type=content_type,
            size_bytes=len(content),
            checksum_sha256=hashlib.sha256(content).hexdigest(),
            ocr_text=_extract_text(content, content_type),
            uploaded_by_id=writer.id,
        )
        db.add(attachment)
        add_audit_event(
            db,
            writer,
            "upload",
            "attachment",
            attachment.id,
            {"record_id": record.id, "filename": original_name, "size_bytes": len(content)},
            record_id=record.id,
            ip=ip,
        )
        db.commit()
        db.refresh(attachment)
        return attachment
    except Exception:
        db.rollback()
        try:
            target.unlink(missing_ok=True)
        except OSError:
            logger.exception("Unable to clean up a failed attachment upload: %s", target.name)
        raise
    finally:
        await file.close()


@router.get("/attachments/{attachment_id}/download")
def download_attachment(attachment_id: str, user: OptionalCurrentUser, db: Database, ip: ClientIP) -> FileResponse:
    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")
    record = _readable_attachment(db, attachment, user)
    path = UPLOAD_DIR / attachment.stored_name
    if not path.is_file():
        logger.error("Attachment metadata exists but stored file is missing: %s", attachment.id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file is unavailable.")
    add_audit_event(
        db,
        user,
        "download",
        "attachment",
        attachment.id,
        {"filename": attachment.original_name},
        record_id=record.id,
        ip=ip,
    )
    db.commit()
    return FileResponse(
        path,
        media_type=attachment.content_type,
        filename=attachment.original_name,
        content_disposition_type="attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.post("/attachments/{attachment_id}/ocr", response_model=AttachmentRead)
def run_ocr(attachment_id: str, writer: RecordWriter, db: Database, ip: ClientIP) -> Attachment:
    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")
    editable_record(db, attachment.record_id, writer)
    if attachment.is_redacted:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Redacted attachments are not indexed.")
    if attachment.content_type not in TEXT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="No OCR engine is configured for PDF and image files. Plain text and CSV files are indexed automatically.",
        )
    path = UPLOAD_DIR / attachment.stored_name
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file is unavailable.")
    attachment.ocr_text = _extract_text(path.read_bytes(), attachment.content_type)
    add_audit_event(
        db, writer, "ocr", "attachment", attachment.id, {"characters": len(attachment.ocr_text)}, record_id=attachment.record_id, ip=ip
    )
    db.commit()
    return attachment


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment_id: str, writer: RecordWriter, db: Database, ip: ClientIP) -> None:
    attachment = db.get(Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")
    editable_record(db, attachment.record_id, writer)
    target = UPLOAD_DIR / attachment.stored_name
    add_audit_event(
        db,
        writer,
        "delete",
        "attachment",
        attachment.id,
        {"record_id": attachment.record_id, "filename": attachment.original_name},
        record_id=attachment.record_id,
        ip=ip,
    )
    db.delete(attachment)
    db.commit()
    try:
        target.unlink(missing_ok=True)
    except OSError:
        logger.exception("Unable to remove deleted attachment %s from disk", attachment_id)
