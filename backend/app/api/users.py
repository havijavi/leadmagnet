from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, hash_password, require_admin
from app.db import get_session
from app.models import User
from app.schemas import UserCreate, UserOut, UserResetPassword, UserUpdate

router = APIRouter()

VALID_ROLES = {"admin", "member", "viewer"}


@router.get("", response_model=list[UserOut])
async def list_users(
    _: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> list[UserOut]:
    rows = await session.scalars(select(User).order_by(User.created_at.desc()))
    return [UserOut.model_validate(r) for r in rows]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(
    payload: UserCreate,
    _: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    if payload.role not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role; valid: {sorted(VALID_ROLES)}")
    if len(payload.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    email = payload.email.lower().strip()
    if "@" not in email:
        raise HTTPException(400, "Invalid email.")

    existing = await session.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(409, "A user with that email already exists.")

    user = User(
        email=email,
        name=payload.name,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    current: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")

    data = payload.model_dump(exclude_unset=True)
    if "role" in data and data["role"] not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role; valid: {sorted(VALID_ROLES)}")

    # Prevent an admin from accidentally locking themselves out.
    if not current.is_superuser and str(user.id) == current.id:
        if data.get("role") and data["role"] != "admin":
            raise HTTPException(400, "You cannot demote yourself.")
        if data.get("is_active") is False:
            raise HTTPException(400, "You cannot disable yourself.")

    for k, v in data.items():
        setattr(user, k, v)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.post("/{user_id}/reset-password", response_model=UserOut)
async def reset_password(
    user_id: UUID,
    payload: UserResetPassword,
    _: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    if len(payload.new_password) < 8:
        raise HTTPException(400, "New password must be at least 8 characters.")
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found.")
    user.password_hash = hash_password(payload.new_password)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    current: CurrentUser = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    if not current.is_superuser and str(user_id) == current.id:
        raise HTTPException(400, "You cannot delete yourself.")
    user = await session.get(User, user_id)
    if user:
        await session.delete(user)
        await session.commit()
