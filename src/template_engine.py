from __future__ import annotations

import sqlite3
from typing import Any

import re
from jinja2 import Environment

from .models import RenderedEmail


ENV = Environment(autoescape=False, trim_blocks=False, lstrip_blocks=False)


def sanitize_template_variables(template: str) -> str:
    def replace_spaces(match):
        content = match.group(1)
        sanitized = content.strip().replace(" ", "_")
        return f"{{{{ {sanitized} }}}}"
    return re.sub(r"\{\{\s*(.*?)\s*\}\}", replace_spaces, template)


def row_to_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def keyword_sentence(contact: dict[str, Any]) -> str:
    keywords = [
        str(contact.get("keyword_1") or "").strip(),
        str(contact.get("keyword_2") or "").strip(),
        str(contact.get("keyword_3") or "").strip(),
    ]
    keywords = [keyword for keyword in keywords if keyword]
    if len(keywords) == 1:
        return keywords[0]
    if len(keywords) == 2:
        return f"{keywords[0]} and {keywords[1]}"
    if len(keywords) >= 3:
        return f"{keywords[0]}, {keywords[1]}, and {keywords[2]}"
    return ""


def contact_context(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    contact = row_to_dict(row)
    context = dict(contact)
    aliases = {
        "First_Name": contact.get("first_name", ""),
        "Last_Name": contact.get("last_name", ""),
        "Full_Name": contact.get("full_name", ""),
        "Email": contact.get("email", ""),
        "Company_Name": contact.get("company_name", ""),
        "Company_Website": contact.get("company_website", ""),
        "LinkedIn": contact.get("linkedin", ""),
        "Title": contact.get("title", ""),
        "Industry": contact.get("industry", ""),
        "Keywords": contact.get("keywords", ""),
        "Country": contact.get("country", ""),
    }
    context.update(aliases)
    context["keyword_sentence"] = keyword_sentence(contact)
    return context


def render_template(template: str, context: dict[str, Any]) -> str:
    sanitized = sanitize_template_variables(template)
    return ENV.from_string(sanitized).render(**context).strip()


def render_email(contact: sqlite3.Row | dict[str, Any], campaign: sqlite3.Row | dict[str, Any]) -> RenderedEmail:
    contact_dict = row_to_dict(contact)
    campaign_dict = row_to_dict(campaign)
    context = contact_context(contact_dict)
    return RenderedEmail(
        recipient_email=str(contact_dict["email"]),
        subject=render_template(str(campaign_dict["subject_template"]), context),
        body=render_template(str(campaign_dict["body_template"]), context),
        used_fallback=False,
    )
