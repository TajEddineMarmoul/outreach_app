from __future__ import annotations

from dataclasses import dataclass

from . import db
from .models import ContactStatus, RenderedEmail
from .template_engine import render_email


@dataclass(frozen=True)
class EmailPreview:
    contact_id: int
    recipient_email: str
    subject: str
    body: str
    used_fallback: bool
    attachment_path: str


def generate_preview(conn, contact_id: int, campaign_id: int | None = None, mark: bool = True) -> EmailPreview:
    contact = db.fetch_contact(conn, contact_id)
    if contact is None:
        raise ValueError(f"Contact {contact_id} not found")
    campaign = db.get_default_campaign(conn) if campaign_id is None else conn.execute(
        "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
    ).fetchone()
    if campaign is None:
        raise ValueError("Campaign not found")

    rendered: RenderedEmail = render_email(contact, campaign)
    if mark:
        db.mark_preview_generated(conn, contact_id, rendered.subject, rendered.body)
    return EmailPreview(
        contact_id=contact_id,
        recipient_email=rendered.recipient_email,
        subject=rendered.subject,
        body=rendered.body,
        used_fallback=rendered.used_fallback,
        attachment_path=str(campaign["attachment_path"] or ""),
    )


def generate_previews(
    conn,
    limit: int = 10,
    statuses: tuple[str, ...] = (ContactStatus.PENDING.value, ContactStatus.APPROVED.value),
) -> list[EmailPreview]:
    contacts = db.fetch_contacts(conn, statuses=statuses, limit=limit)
    return [generate_preview(conn, int(contact["id"]), mark=True) for contact in contacts]


def approve_contacts(conn, contact_ids: list[int]) -> int:
    approved = 0
    for contact_id in contact_ids:
        contact = db.fetch_contact(conn, contact_id)
        if not contact:
            continue
        if contact["preview_generated_at"] and contact["status"] == ContactStatus.PENDING.value:
            db.set_contact_status(conn, contact_id, ContactStatus.APPROVED.value)
            approved += 1
    return approved


def approve_first_n(conn, n: int) -> int:
    contacts = db.fetch_contacts(conn, statuses=(ContactStatus.PENDING.value,), limit=n)
    contact_ids: list[int] = []
    for contact in contacts:
        generated = generate_preview(conn, int(contact["id"]), mark=True)
        contact_ids.append(generated.contact_id)
    return approve_contacts(conn, contact_ids)


def reject_contacts(conn, contact_ids: list[int]) -> int:
    from .dnc import add_email

    rejected = 0
    for contact_id in contact_ids:
        contact = db.fetch_contact(conn, contact_id)
        if not contact:
            continue
        if add_email(conn, str(contact["email"]), "Rejected in preview"):
            rejected += 1
    return rejected
