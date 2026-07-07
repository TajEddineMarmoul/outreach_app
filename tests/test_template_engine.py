from __future__ import annotations

from pathlib import Path

from src import db
from src.models import ContactStatus
from src.template_engine import render_email


def insert_contact(conn, email: str, keywords: str = "", **extra):
    keyword_parts = [part.strip() for part in keywords.split(",") if part.strip()]
    keyword_parts = (keyword_parts + ["", "", ""])[:3]
    db.insert_contact(
        conn,
        {
            "first_name": "Alex",
            "email": email,
            "company_name": "Acme",
            "keywords": keywords,
            "keyword_1": keyword_parts[0],
            "keyword_2": keyword_parts[1],
            "keyword_3": keyword_parts[2],
            "status": ContactStatus.PENDING.value,
            **extra,
        },
    )
    return db.fetch_contact_by_email(conn, email)


def test_template_rendering_uses_keyword_body(tmp_path: Path) -> None:
    conn = db.init_db(tmp_path / "outreach.db")
    contact = insert_contact(
        conn,
        "taj@example.com",
        "plant-based drinks, farm transition, dairy alternatives",
    )
    rendered = render_email(contact, db.get_default_campaign(conn))

    assert rendered.used_fallback is False
    assert rendered.subject == "Junior technical profile - Acme"
    assert "plant-based drinks, farm transition, and dairy alternatives" in rendered.body


def test_fallback_template_is_used_when_keywords_are_missing(tmp_path: Path) -> None:
    conn = db.init_db(tmp_path / "outreach.db")
    contact = insert_contact(conn, "fallback@example.com")
    rendered = render_email(contact, db.get_default_campaign(conn))

    assert rendered.used_fallback is False
    assert "I found your LinkedIn profile while looking at Acme" in rendered.body
