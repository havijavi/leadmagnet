"""Auth primitives.

Three roles ranked by privilege:
  admin  - everything (system config, user mgmt)
  member - daily pipeline ops (discovery, enrichment, leads, outreach, csv import)
  viewer - read-only

Bearer-token strategy:
  - Per-user JWT issued at /api/auth/login (HS256, signed with effective_jwt_secret)
  - The .env ADMIN_TOKEN is a "superuser bypass" — anyone presenting it is
    treated as admin without a user account. Useful for setup-vps.sh, CI,
    and emergency access.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import bcrypt
import jwt
from fastapi import Header, HTTPException, status

from app.config import settings


# ---------- password hashing ----------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------- JWT ----------

def create_access_token(user_id: str, email: str, role: str) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + settings.JWT_TTL_SECONDS,
    }
    return jwt.encode(payload, settings.effective_jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.effective_jwt_secret, algorithms=["HS256"])


# ---------- current user ----------

@dataclass
class CurrentUser:
    id: str
    email: str
    role: str
    name: Optional[str] = None
    is_superuser: bool = False  # true when authenticated via ADMIN_TOKEN bypass

    def has_role(self, *allowed: str) -> bool:
        if self.role == "admin" or self.is_superuser:
            return True
        return self.role in allowed


SUPERUSER_ID = "00000000-0000-0000-0000-000000000000"


def _make_role_dep(*allowed: str):
    """Build a FastAPI dependency that requires one of the given roles."""

    async def _dep(authorization: str = Header(default="")) -> CurrentUser:
        if not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing bearer token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token = authorization[len("Bearer "):].strip()
        if not token:
            raise HTTPException(401, "Empty bearer token.")

        # Superuser bypass via .env ADMIN_TOKEN.
        if settings.ADMIN_TOKEN and token == settings.ADMIN_TOKEN:
            return CurrentUser(
                id=SUPERUSER_ID,
                email="superuser@local",
                role="admin",
                name="Superuser (env token)",
                is_superuser=True,
            )

        # JWT path.
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "Token expired — sign in again.")
        except jwt.PyJWTError as e:
            raise HTTPException(401, f"Invalid token: {e}")

        user = CurrentUser(
            id=str(payload.get("sub", "")),
            email=str(payload.get("email", "")),
            role=str(payload.get("role", "")),
        )
        if not user.role:
            raise HTTPException(401, "Token missing role.")
        if not user.has_role(*allowed):
            raise HTTPException(
                403,
                f"Role '{user.role}' cannot access this — required: {sorted(set(allowed))}",
            )
        return user

    return _dep


# Three reusable dependencies. Always import these — don't call _make_role_dep
# inline, otherwise FastAPI builds a fresh dep object per import site.
require_admin = _make_role_dep("admin")
require_member = _make_role_dep("admin", "member")
require_any = _make_role_dep("admin", "member", "viewer")
