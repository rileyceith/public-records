import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import token_digest
from app.core.config import PUBLIC_MODE
from app.database import get_db
from app.models import AuthSession, User


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[7:].strip()
    if not token or len(token) > 256:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.")

    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_digest(token)))
    if not session or session.expires_at <= int(time.time()):
        if session:
            db.delete(session)
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not session.user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account is disabled.")
    return session.user


def get_optional_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User | None:
    if not authorization:
        return None
    return get_current_user(authorization, db)


def require_roles(*roles: str):
    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to do that.")
        return user

    return checker


def client_ip(request: Request) -> str:
    if PUBLIC_MODE:
        forwarded = request.headers.get("cf-connecting-ip")
        if forwarded:
            return forwarded
    return request.client.host if request.client else ""


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalCurrentUser = Annotated[User | None, Depends(get_optional_current_user)]
AdminUser = Annotated[User, Depends(require_roles("admin"))]
RecordWriter = Annotated[User, Depends(require_roles("clerk", "admin"))]
AuditReader = Annotated[User, Depends(require_roles("admin", "auditor"))]
ClientIP = Annotated[str, Depends(client_ip)]
