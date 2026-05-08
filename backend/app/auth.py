from fastapi import Header, HTTPException, status

from app.config import settings


async def require_admin(authorization: str = Header(default="")) -> None:
    expected = f"Bearer {settings.ADMIN_TOKEN}"
    if not settings.ADMIN_TOKEN or authorization != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
