"""SMTP sender. Any provider that speaks STARTTLS/SMTP works."""
from __future__ import annotations

import logging
from email.message import EmailMessage
from typing import Optional

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)


class EmailerError(RuntimeError):
    pass


class Emailer:
    @property
    def configured(self) -> bool:
        return bool(settings.SMTP_HOST and settings.SMTP_FROM)

    async def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        reply_to: Optional[str] = None,
    ) -> None:
        if not self.configured:
            raise EmailerError(
                "SMTP not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM in .env."
            )

        msg = EmailMessage()
        from_header = (
            f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM}>"
            if settings.SMTP_FROM_NAME
            else settings.SMTP_FROM
        )
        msg["From"] = from_header
        msg["To"] = to
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.set_content(body)

        try:
            await aiosmtplib.send(
                msg,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER or None,
                password=settings.SMTP_PASSWORD or None,
                start_tls=settings.SMTP_PORT == 587,
                use_tls=settings.SMTP_PORT == 465,
                timeout=30,
            )
        except Exception as e:
            logger.error("SMTP send failed to %s: %s", to, e)
            raise EmailerError(str(e)) from e


emailer = Emailer()
