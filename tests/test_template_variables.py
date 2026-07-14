from __future__ import annotations

import pytest

from src.template_engine import (
    MissingTemplateVariablesError,
    contact_context,
    extract_template_variables,
    render_template,
)


def test_template_headers_with_spaces_and_underscores_are_distinct() -> None:
    template = "{{ First Name }} / {{ First_Name }}"
    context = {
        "First Name": "Sandy",
        "First_Name": "Sandra",
    }

    assert extract_template_variables(template) == ["First Name", "First_Name"]
    assert render_template(template, context) == "Sandy / Sandra"


def test_strict_render_rejects_the_exact_missing_header() -> None:
    with pytest.raises(MissingTemplateVariablesError) as exc_info:
        render_template("Hello {{ First Name }}", {"First_Name": "Sandy"}, strict=True)

    assert exc_info.value.variables == ("First Name",)


def test_contact_context_does_not_invent_header_aliases() -> None:
    context = contact_context(
        {
            "email": "lead@example.com",
            "first_name": "Legacy value",
            "custom_fields": {"First Name": "Sandy"},
        }
    )

    assert context["First Name"] == "Sandy"
    assert "First_Name" not in context
    assert context["email"] == "lead@example.com"
