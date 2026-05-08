"""CSV target-list import.

Accepts any reasonable header row; we map case-insensitively. Recognized
columns: name, company, email, website, domain, linkedin_url / linkedin,
role / title, location, tags (comma-separated).

Each row becomes a Lead with status='new', enrichment_status='pending'. The
fingerprint dedupes against existing leads, so re-uploading the same file is
a no-op.
"""
from __future__ import annotations

import csv
import io
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import select

from app.db import session_scope
from app.models import Lead, TargetList
from app.services.extractor import fingerprint_lead

logger = logging.getLogger(__name__)


COLUMN_ALIASES = {
    "name": ["name", "full name", "fullname", "contact"],
    "company": ["company", "organization", "org", "employer"],
    "email": ["email", "email address", "e-mail"],
    "website": ["website", "site", "url", "company website"],
    "domain": ["domain"],
    "linkedin_url": ["linkedin_url", "linkedin", "linkedin url"],
    "role": ["role", "title", "job title", "position"],
    "location": ["location", "city", "country"],
    "tags": ["tags", "labels"],
}


async def import_csv(
    csv_bytes: bytes,
    *,
    list_name: str,
    list_description: Optional[str] = None,
) -> dict:
    decoded = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        return {"ok": False, "reason": "empty CSV"}

    field_map = _build_field_map(reader.fieldnames)
    if "email" not in field_map.values() and "domain" not in field_map.values() and "website" not in field_map.values():
        return {"ok": False, "reason": "CSV needs at least one of: email, domain, website"}

    async with session_scope() as session:
        target_list = TargetList(name=list_name, description=list_description, row_count=0)
        session.add(target_list)
        await session.flush()

        added = 0
        skipped = 0
        for row in reader:
            mapped = {dest: (row.get(src) or "").strip() for src, dest in field_map.items()}
            if not (mapped.get("email") or mapped.get("domain") or mapped.get("website") or mapped.get("name")):
                skipped += 1
                continue

            tags = []
            if mapped.get("tags"):
                tags = [t.strip() for t in mapped["tags"].split(",") if t.strip()]

            lookup = {
                "email": mapped.get("email") or None,
                "website": mapped.get("website") or None,
                "name": mapped.get("name") or None,
                "source_url": "csv://" + list_name,
            }
            fp = fingerprint_lead(lookup)

            existing = await session.scalar(select(Lead).where(Lead.fingerprint == fp))
            if existing:
                skipped += 1
                continue

            lead = Lead(
                target_list_id=target_list.id,
                name=mapped.get("name") or None,
                company=mapped.get("company") or None,
                email=mapped.get("email") or None,
                website=mapped.get("website") or None,
                domain=mapped.get("domain") or _domain_of(mapped.get("website") or mapped.get("email")),
                linkedin_url=mapped.get("linkedin_url") or None,
                role=mapped.get("role") or None,
                location=mapped.get("location") or None,
                fingerprint=fp,
                tags=tags,
                status="new",
                enrichment_status="pending",
                source_url=f"csv://{list_name}",
            )
            session.add(lead)
            added += 1

        target_list.row_count = added

    return {"ok": True, "list_id": str(target_list.id), "added": added, "skipped": skipped}


def _build_field_map(headers: list[str]) -> dict[str, str]:
    """Map original CSV header → our internal column name."""
    out: dict[str, str] = {}
    for h in headers:
        if not h:
            continue
        norm = h.strip().lower()
        for dest, aliases in COLUMN_ALIASES.items():
            if norm in aliases or norm.replace(" ", "_") == dest:
                out[h] = dest
                break
    return out


def _domain_of(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    if "@" in s:
        return s.split("@", 1)[1].lower()
    out = s.lower().replace("https://", "").replace("http://", "").split("/")[0]
    return out[4:] if out.startswith("www.") else out or None
