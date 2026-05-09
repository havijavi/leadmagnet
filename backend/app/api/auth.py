from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    CurrentUser,
    SUPERUSER_ID,
    create_access_token,
    hash_password,
    require_any,
    verify_password,
)
from app.config import settings
from app.db import get_session
from app.models import User
from app.schemas import (
    LoginRequest,
    LoginResponse,
    NeedsSetupOut,
    PasswordChange,
    SetupRequest,
    UserOut,
)

router = APIRouter()


# ---------- public endpoints (no auth) ----------

@router.get("/needs-setup", response_model=NeedsSetupOut)
async def needs_setup(session: AsyncSession = Depends(get_session)) -> NeedsSetupOut:
    """Tell the frontend whether to route to /setup or /login."""
    count = await session.scalar(select(func.count(User.id))) or 0
    return NeedsSetupOut(needs_setup=count == 0)


@router.post("/setup", response_model=LoginResponse, status_code=201)
async def setup(payload: SetupRequest, session: AsyncSession = Depends(get_session)) -> LoginResponse:
    """First-run admin creation. Refuses if any users already exist."""
    count = await session.scalar(select(func.count(User.id))) or 0
    if count > 0:
        raise HTTPException(400, "Setup already complete — sign in instead.")

    email = payload.email.lower().strip()
    if "@" not in email:
        raise HTTPException(400, "Invalid email.")
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")

    user = User(
        email=email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role="admin",
        is_active=True,
        last_login_at=datetime.now(timezone.utc),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(str(user.id), user.email, user.role)
    return LoginResponse(
        token=token,
        expires_in=settings.JWT_TTL_SECONDS,
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_session)) -> LoginResponse:
    email = payload.email.lower().strip()
    user = await session.scalar(select(User).where(User.email == email))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        # Identical 401 either way to avoid leaking which emails are registered.
        raise HTTPException(401, "Invalid email or password.")

    user.last_login_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(user)

    token = create_access_token(str(user.id), user.email, user.role)
    return LoginResponse(
        token=token,
        expires_in=settings.JWT_TTL_SECONDS,
        user=UserOut.model_validate(user),
    )


# ---------- authenticated ----------

@router.get("/me", response_model=UserOut)
async def me(
    current: CurrentUser = Depends(require_any),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    if current.is_superuser:
        # Synthesize a UserOut for the env-token superuser so the frontend
        # can render a consistent header even when no DB user exists yet.
        return UserOut(
            id=UUID(SUPERUSER_ID),
            email=current.email,
            name=current.name or "Superuser (env token)",
            role="admin",
            is_active=True,
            last_login_at=None,
            created_at=datetime.now(timezone.utc),
        )
    user = await session.get(User, UUID(current.id))
    if not user:
        raise HTTPException(404, "User not found.")
    return UserOut.model_validate(user)


@router.post("/change-password")
async def change_password(
    payload: PasswordChange,
    current: CurrentUser = Depends(require_any),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if current.is_superuser:
        raise HTTPException(
            400,
            "Superuser is authenticated by ADMIN_TOKEN — change it in .env, not here.",
        )
    if len(payload.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters.")
    user = await session.get(User, UUID(current.id))
    if not user or not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(401, "Old password is incorrect.")
    user.password_hash = hash_password(payload.new_password)
    await session.commit()
    return {"ok": True}
