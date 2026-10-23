import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import add_audit_event
from app.core.config import SESSION_TTL_SECONDS
from app.core.security import hash_password, new_session_token, token_digest, verify_password
from app.database import get_db
from app.dependencies import AdminUser, ClientIP, CurrentUser
from app.models import Agency, AuthSession, User
from app.schemas import LoginResponse, UserCreate, UserLogin, UserRead, UserRegister, UserUpdate


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])
Database = Annotated[Session, Depends(get_db)]

MAX_LOGIN_FAILURES = 5
LOGIN_WINDOW_SECONDS = 300
_login_failures: dict[str, list[float]] = {}


def _recent_failures(key: str) -> list[float]:
    cutoff = time.monotonic() - LOGIN_WINDOW_SECONDS
    recent = [stamp for stamp in _login_failures.get(key, []) if stamp > cutoff]
    if recent:
        _login_failures[key] = recent
    else:
        _login_failures.pop(key, None)
    return recent


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Database, ip: ClientIP) -> User:
    """Self-service sign-up creates an unverified citizen; staff must verify identity before records can be requested."""
    if db.scalar(select(User.id).where(User.email == payload.email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with that email already exists.")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role="citizen",
    )
    db.add(user)
    try:
        db.flush()
        add_audit_event(db, user, "register", "user", str(user.id), ip=ip)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with that email already exists.") from error
    db.refresh(user)
    return user


@router.post("/login", response_model=LoginResponse)
def login(payload: UserLogin, db: Database, ip: ClientIP) -> LoginResponse:
    throttle_key = f"{ip}|{payload.email.lower()}"
    if len(_recent_failures(throttle_key)) >= MAX_LOGIN_FAILURES:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many failed sign-in attempts. Try again in a few minutes.")
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        _login_failures.setdefault(throttle_key, []).append(time.monotonic())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    _login_failures.pop(throttle_key, None)
    token = new_session_token()
    now = int(time.time())
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    db.add(AuthSession(token_hash=token_digest(token), user_id=user.id, expires_at=now + SESSION_TTL_SECONDS))
    add_audit_event(db, user, "login", "user", str(user.id), ip=ip)
    db.commit()
    return LoginResponse(
        access_token=token,
        expires_in=SESSION_TTL_SECONDS,
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
def current_user(user: CurrentUser) -> User:
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: CurrentUser, authorization: Annotated[str, Header()], db: Database) -> None:
    token = authorization[7:].strip()
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_digest(token)))
    if session:
        db.delete(session)
        add_audit_event(db, user, "logout", "user", str(user.id))
        db.commit()


def _check_staff_agency(db: Session, role: str, agency_id: int | None) -> None:
    if role == "clerk" and not agency_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Clerks must belong to an agency.")
    if agency_id is not None and not db.get(Agency, agency_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Choose a valid agency.")


@router.patch("/users/{user_id}", response_model=UserRead, tags=["Users"])
def update_user(user_id: int, payload: UserUpdate, admin: AdminUser, db: Database, ip: ClientIP) -> User:
    """Change a role, agency or active flag, or verify a citizen's identity."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    changes = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and (changes.get("role", "admin") != "admin" or changes.get("is_active") is False):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="You cannot demote or disable your own account.")
    _check_staff_agency(db, changes.get("role", user.role), changes.get("agency_id", user.agency_id))
    for field, value in changes.items():
        setattr(user, field, value)
    add_audit_event(db, admin, "update", "user", str(user.id), changes, ip=ip)
    db.commit()
    return user


@router.get("/users", response_model=list[UserRead], tags=["Users"])
def list_users(
    _admin: AdminUser,
    db: Database,
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc(), User.id.desc())).all())


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED, tags=["Users"])
def create_user(
    payload: UserCreate,
    admin: AdminUser,
    db: Database,
) -> User:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with that email already exists.")
    _check_staff_agency(db, payload.role, payload.agency_id)

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        agency_id=payload.agency_id,
        is_verified=payload.is_verified or payload.role != "citizen",
    )
    db.add(user)
    try:
        db.flush()
        add_audit_event(
            db,
            admin,
            "create",
            "user",
            str(user.id),
            {"email": user.email, "role": user.role},
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        logger.info("User creation conflicted with an existing email address.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with that email already exists.",
        ) from error
    db.refresh(user)
    return user
