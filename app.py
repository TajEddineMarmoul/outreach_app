from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from src import db
from src.analytics import export_send_log, send_log_dataframe
from src.dnc import add_email, import_dnc_csv, rows as dnc_rows
from src.gmail_sender import (
    connect_and_get_profile,
    connect_sender_account,
    credentials_file_path,
    default_token_path,
    gmail_connection_status,
)
from src.google_sheets import (
    connect_google_sheets_oauth,
    get_public_sheet_csv,
    get_published_csv,
    list_sheet_tabs,
    parse_google_sheet_url_details,
    read_sheet_rows,
    sheets_connection_status,
    sheets_credentials_paths,
)
from src.importer import clean_cell, detect_columns, extract_keywords, import_csv, import_dataframe, normalize_email
from src.models import (
    AppConfig,
    ContactStatus,
    DEFAULT_BODY_TEMPLATE,
    DEFAULT_FALLBACK_BODY_TEMPLATE,
    DEFAULT_SUBJECT_TEMPLATE,
    load_config,
    save_config,
)
from src.preview import approve_contacts, generate_preview, reject_contacts
from src.scheduler import (
    pause_autopilot,
    resume_autopilot,
    run_autopilot_loop,
    send_next_approved,
    send_test_email,
    start_autopilot,
    start_background_autopilot,
    stop_autopilot,
)
from src.safety import (
    attachment_check,
    effective_daily_cap,
    effective_sender_daily_cap,
    next_send_time,
    sent_today_for_sender,
    sent_today_local,
    campaign_checklist,
)


ROOT = Path(__file__).resolve().parent
SIDEBAR_PAGES = ["Campaigns", "Templates", "Contacts", "Analytics", "Settings"]

MAPPING_FIELDS = [
    ("email", "Email column", True),
    ("first_name", "First Name column", True),
    ("company_name", "Company Name column", True),
    ("keywords", "Keywords column", False),
    ("linkedin", "LinkedIn column", False),
    ("title", "Title column", False),
    ("country", "Country column", False),
    ("last_name", "Last Name column", False),
    ("full_name", "Full Name column", False),
    ("industry", "Industry column", False),
]

VARIABLES = [
    "{{ First_Name }}",
    "{{ Company_Name }}",
    "{{ keyword_sentence }}",
    "{{ Email }}",
    "{{ LinkedIn }}",
    "{{ Title }}",
    "{{ Country }}",
    "{{ keyword_1 }}",
    "{{ keyword_2 }}",
    "{{ keyword_3 }}",
]

_WARN = "\u26a0\ufe0f"
_CHECK = "\u2705"
_DASH = "\u2013"
_DOT = "\u00b7"


def config_path() -> Path:
    return db.resolve_project_path(os.getenv("OUTREACH_CONFIG_PATH", "config.yaml"), ROOT)


def database_path() -> Path:
    return db.get_db_path(os.getenv("OUTREACH_DB_PATH", "data/outreach.db"))


def app_context() -> tuple[object, AppConfig]:
    load_dotenv(ROOT / ".env")
    conn = db.init_db(database_path())
    config = load_config(config_path())
    db.get_default_campaign(conn)
    upgrade_legacy_campaign_bodies(conn)
    return conn, config


def upgrade_legacy_campaign_bodies(conn) -> None:
    for campaign in db.list_campaigns(conn):
        subject = str(campaign["subject_template"])
        body = str(campaign["body_template"])
        fallback = str(campaign["fallback_body_template"])
        attachment_path = str(campaign["attachment_path"] or "")
        markers = (
            "{% if keyword_3",
            "{% elif keyword_2",
            "Junior profile -",
            "CV_fullstack_ai",
        )
        has_old_profile_link = (
            ("linkedin.com/in/" in body and "linkedin.com/in/your-profile" not in body)
            or ("github.com/" in body and "github.com/your-handle" not in body)
            or ("linkedin.com/in/" in fallback and "linkedin.com/in/your-profile" not in fallback)
            or ("github.com/" in fallback and "github.com/your-handle" not in fallback)
        )
        has_legacy_marker = any(
            marker in subject or marker in body or marker in fallback or marker in attachment_path
            for marker in markers
        )
        if has_legacy_marker or has_old_profile_link:
            db.update_campaign(
                conn,
                int(campaign["id"]),
                DEFAULT_SUBJECT_TEMPLATE,
                DEFAULT_BODY_TEMPLATE,
                DEFAULT_FALLBACK_BODY_TEMPLATE,
                "data/uploads/resume.pdf",
            )


def run_cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Safe local Gmail outreach campaign tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import-csv")
    import_parser.add_argument("csv_path")

    preview_parser = subparsers.add_parser("preview")
    preview_parser.add_argument("--limit", type=int, default=5)

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("--limit", type=int, default=20)

    send_once_parser = subparsers.add_parser("send-once")
    send_once_parser.add_argument("--limit", type=int, default=1)

    subparsers.add_parser("run-autopilot")
    subparsers.add_parser("pause")
    subparsers.add_parser("resume")
    subparsers.add_parser("status")

    export_parser = subparsers.add_parser("export-log")
    export_parser.add_argument("csv_path")

    dnc_parser = subparsers.add_parser("dnc")
    dnc_subparsers = dnc_parser.add_subparsers(dest="dnc_command", required=True)
    dnc_add = dnc_subparsers.add_parser("add")
    dnc_add.add_argument("email")
    dnc_add.add_argument("--reason", default="Manual DNC")
    dnc_import = dnc_subparsers.add_parser("import")
    dnc_import.add_argument("csv_path")

    args = parser.parse_args(argv)
    conn, config = app_context()

    if args.command == "import-csv":
        result = import_csv(args.csv_path, conn)
        print(result.model_dump())
        return 0
    if args.command == "preview":
        campaign = db.get_default_campaign(conn)
        contacts = db.campaign_contacts(conn, int(campaign["id"]), limit=args.limit) or db.fetch_contacts(conn, limit=args.limit)
        for contact in contacts:
            item = generate_preview(conn, int(contact["id"]), campaign_id=int(campaign["id"]), mark=True)
            print(f"\nTo: {item.recipient_email}\nSubject: {item.subject}\n\n{item.body}\n")
        print(f"generated: {len(contacts)}")
        return 0
    if args.command == "approve":
        campaign = db.get_default_campaign(conn)
        contacts = db.campaign_contacts(conn, int(campaign["id"]), statuses=(ContactStatus.PENDING.value,), limit=args.limit)
        ids = [int(contact["id"]) for contact in contacts]
        for contact_id in ids:
            generate_preview(conn, contact_id, campaign_id=int(campaign["id"]), mark=True)
        print(f"approved: {approve_contacts(conn, ids)}")
        return 0
    if args.command == "send-once":
        campaign = db.get_default_campaign(conn)
        sender_email = db.get_setting(conn, "sender_email", "")
        sent = 0
        for _ in range(args.limit):
            ok, message = send_next_approved(
                conn,
                config,
                sender_email=sender_email,
                campaign_id=int(campaign["id"]),
            )
            print(message)
            if not ok:
                break
            sent += 1
        print(f"sent: {sent}")
        return 0
    if args.command == "run-autopilot":
        run_autopilot_loop(database_path(), config_path())
        return 0
    if args.command == "pause":
        pause_autopilot(conn)
        print("autopilot_status: paused")
        return 0
    if args.command == "resume":
        resume_autopilot(conn)
        print("autopilot_status: active")
        return 0
    if args.command == "status":
        print_status(conn, config)
        return 0
    if args.command == "export-log":
        output = export_send_log(conn, args.csv_path)
        print(f"exported: {output}")
        return 0
    if args.command == "dnc" and args.dnc_command == "add":
        print(f"added: {add_email(conn, args.email, args.reason)}")
        return 0
    if args.command == "dnc" and args.dnc_command == "import":
        print(f"imported: {import_dnc_csv(conn, args.csv_path)}")
        return 0
    return 1


def print_status(conn, config: AppConfig) -> None:
    counts = db.count_contacts_by_status(conn)
    for key in ["total", "pending", "approved", "sent", "replied", "bounced", "failed", "do_not_contact"]:
        print(f"{key}: {counts.get(key, 0)}")
    sent_today = sent_today_local(conn, config)
    cap = effective_daily_cap(conn, config)
    print(f"sent_today: {sent_today}")
    print(f"remaining_today: {max(cap - sent_today, 0)}")
    print(f"next_scheduled_send_time: {next_send_time(config)}")
    print(f"active_campaigns: {len([c for c in db.list_campaigns(conn) if c['status'] in {'active', 'running'}])}")


def run_streamlit() -> None:
    import streamlit as st

    st.set_page_config(page_title="Job Outreach Sender", layout="wide")
    conn, config = app_context()
    inject_styles(st)

    if "sidebar_page" not in st.session_state:
        st.session_state["sidebar_page"] = "Campaigns"

    st.sidebar.title("Outreach")
    page = st.sidebar.radio("Navigation", SIDEBAR_PAGES, key="sidebar_page")

    if page == "Campaigns":
        campaigns_page(st, conn, config)
    elif page == "Templates":
        templates_page(st, conn)
    elif page == "Contacts":
        contacts_page(st, conn)
    elif page == "Analytics":
        analytics_page(st, conn, config)
    elif page == "Settings":
        settings_page(st, conn, config)

    if st.session_state.get("show_gmail_setup_modal"):
        gmail_setup_dialog(st, conn)


def inject_styles(st) -> None:
    st.markdown(
        """
        <style>
        .small-note {
            color: #64748b;
            font-size: 0.85rem;
            margin-top: -0.3rem;
        }
        .muted-badge {
            display: inline-flex;
            align-items: center;
            background-color: #f1f5f9;
            color: #475569;
            font-size: 0.75rem;
            font-weight: 600;
            padding: 2px 10px;
            border-radius: 9999px;
            border: 1px solid #e2e8f0;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        /* Premium title styling */
        input[id^="header_name_field"] {
            font-size: 1.8rem !important;
            font-weight: 700 !important;
            border: none !important;
            background: transparent !important;
            padding: 0 !important;
            margin: 0 !important;
            color: #0f172a !important;
            box-shadow: none !important;
        }
        input[id^="header_name_field"]:focus {
            outline: none !important;
            border-bottom: 2px solid #2563eb !important;
            border-radius: 0 !important;
        }
        
        /* Blue pill for recipients selection */
        .to-pill-btn button {
            background-color: #eff6ff !important;
            color: #2563eb !important;
            border: 1px solid #bfdbfe !important;
            border-radius: 9999px !important;
            padding: 2px 12px !important;
            font-weight: 500 !important;
            font-size: 0.85rem !important;
            min-height: 28px !important;
            height: 28px !important;
            line-height: 1 !important;
        }
        .to-pill-btn button:hover {
            background-color: #dbeafe !important;
            border-color: #3b82f6 !important;
        }
        
        /* Borderless clean subject input */
        .subject-input input {
            border: none !important;
            border-bottom: 1px solid #f1f5f9 !important;
            border-radius: 0 !important;
            padding: 6px 0 !important;
            background: transparent !important;
            font-size: 1rem !important;
            box-shadow: none !important;
        }
        .subject-input input:focus {
            border-bottom: 1px solid #2563eb !important;
        }
        
        /* Clean body textarea writing sheet */
        .body-textarea textarea {
            border: none !important;
            border-top: 1px solid #e2e8f0 !important;
            border-radius: 0 0 6px 6px !important;
            padding: 12px !important;
            font-size: 0.95rem !important;
            box-shadow: none !important;
            background-color: #ffffff !important;
        }
        
        /* Dropdown button styling for From and File */
        .from-dropdown-btn button {
            background-color: transparent !important;
            border: none !important;
            color: #0f172a !important;
            font-size: 0.95rem !important;
            font-weight: 400 !important;
            padding: 4px 0 !important;
            text-align: left !important;
            box-shadow: none !important;
            min-height: auto !important;
            height: auto !important;
        }
        .from-dropdown-btn button:hover {
            color: #2563eb !important;
            background-color: transparent !important;
        }
        
        /* Toolbar buttons styling */
        .toolbar-btn button {
            background-color: #f8fafc !important;
            border: 1px solid #e2e8f0 !important;
            color: #475569 !important;
            font-size: 0.85rem !important;
            padding: 4px 10px !important;
            border-radius: 6px !important;
        }
        .toolbar-btn button:hover {
            background-color: #f1f5f9 !important;
            color: #0f172a !important;
            border-color: #cbd5e1 !important;
        }
        
        /* Standard buttons styling */
        .stButton > button {
            padding: 0.25rem 0.75rem;
            font-size: 0.85rem !important;
            border-radius: 6px !important;
            font-weight: 500 !important;
            transition: all 0.2s ease !important;
        }
        
        div[data-testid="stVerticalBlock"] > div {
            padding-top: 0.2rem;
            padding-bottom: 0.2rem;
        }
        div[data-testid="stExpander"] {
            margin-top: 0.25rem;
            margin-bottom: 0.25rem;
        }
        .stMetric {
            padding: 0;
        }
        h3 {
            margin-top: 0.5rem;
            margin-bottom: 0.3rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def read_credentials_json() -> dict[str, Any] | None:
    path = credentials_file_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def oauth_client_type() -> str:
    data = read_credentials_json()
    if not data:
        return "unknown"
    if isinstance(data.get("installed"), dict):
        return "desktop"
    if isinstance(data.get("web"), dict):
        return "web"
    if data.get("client_id") and data.get("client_secret"):
        return "desktop"
    return "unknown"


def normalize_desktop_credentials(data: dict[str, Any]) -> tuple[bool, str, dict[str, Any] | None]:
    if isinstance(data.get("installed"), dict):
        installed = data["installed"]
    elif data.get("client_id") and data.get("client_secret"):
        installed = data
    elif isinstance(data.get("web"), dict):
        return False, "This looks like a Web application OAuth client. Create a Desktop app client for this local app.", None
    else:
        return False, "This file does not look like a Google OAuth Desktop client JSON.", None

    client_id = str(installed.get("client_id", "")).strip()
    client_secret = str(installed.get("client_secret", "")).strip()
    if not client_id or not client_secret:
        return False, "The OAuth file must include both client_id and client_secret.", None

    normalized = {
        "installed": {
            "client_id": client_id,
            "project_id": str(installed.get("project_id", "")),
            "auth_uri": str(installed.get("auth_uri", "https://accounts.google.com/o/oauth2/auth")),
            "token_uri": str(installed.get("token_uri", "https://oauth2.googleapis.com/token")),
            "auth_provider_x509_cert_url": str(
                installed.get(
                    "auth_provider_x509_cert_url",
                    "https://www.googleapis.com/oauth2/v1/certs",
                )
            ),
            "client_secret": client_secret,
            "redirect_uris": installed.get("redirect_uris") or ["http://localhost"],
        }
    }
    return True, "", normalized


def save_credentials_json(data: dict[str, Any]) -> tuple[bool, str]:
    ok, message, normalized = normalize_desktop_credentials(data)
    if not ok or normalized is None:
        return False, message
    path = credentials_file_path()
    path.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    return True, "credentials.json saved"


def save_manual_credentials(client_id: str, client_secret: str) -> tuple[bool, str]:
    if not client_id.strip() and not client_secret.strip():
        return False, "Client ID and client secret are required, or upload the downloaded JSON file."
    if not client_id.strip() or not client_secret.strip():
        return False, "Client secret is also required, or upload the downloaded JSON file."
    return save_credentials_json(
        {
            "installed": {
                "client_id": client_id.strip(),
                "project_id": "",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": client_secret.strip(),
                "redirect_uris": ["http://localhost"],
            }
        }
    )


def wizard_oauth_status_rows() -> list[dict[str, str]]:
    gmail_status = gmail_connection_status()
    sheets_status = sheets_connection_status()
    _, sheets_token = sheets_credentials_paths()
    return [
        {
            "Item": "credentials.json",
            "Status": "found" if credentials_file_path().exists() else "missing",
        },
        {"Item": "OAuth client type", "Status": oauth_client_type()},
        {"Item": "Gmail token", "Status": "found" if default_token_path().exists() else "missing"},
        {"Item": "Connected Gmail email", "Status": gmail_status.email or "not connected"},
        {"Item": "Google Sheets token", "Status": "found" if sheets_token.exists() else "missing"},
        {"Item": "Google Sheets connected", "Status": "yes" if sheets_status.connected else "no"},
    ]


def oauth_status_panel(st, conn) -> None:
    gmail_credentials = credentials_file_path()
    gmail_default_token = default_token_path()
    sheets_credentials, sheets_token = sheets_credentials_paths()
    default_gmail = gmail_connection_status()
    sheets_status = sheets_connection_status()
    rows = [
        {"Item": "Gmail credentials file", "Status": "found" if gmail_credentials.exists() else "missing", "Path/detail": str(gmail_credentials)},
        {"Item": "Gmail token file", "Status": "found" if gmail_default_token.exists() else "missing", "Path/detail": str(gmail_default_token)},
        {"Item": "Gmail connected email", "Status": default_gmail.email or "not connected", "Path/detail": default_gmail.status},
        {"Item": "Google Sheets credentials file", "Status": "found" if sheets_credentials.exists() else "missing", "Path/detail": str(sheets_credentials)},
        {"Item": "Google Sheets token file", "Status": "found" if sheets_token.exists() else "missing", "Path/detail": str(sheets_token)},
        {"Item": "Google Sheets connected", "Status": "yes" if sheets_status.connected else "no", "Path/detail": sheets_status.status},
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    senders = db.list_senders(conn)
    if senders:
        st.write("Connected Gmail senders")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Email": sender["email"],
                        "Display name": sender["display_name"],
                        "Status": sender["status"],
                        "Daily cap": sender["daily_cap"],
                        "Default": bool(sender["is_default"]),
                        "Token path": sender["token_path"],
                    }
                    for sender in senders
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


def credentials_available() -> bool:
    return credentials_file_path().exists()


def register_connected_sender(conn, status, display_name: str = "Default sender") -> int:
    sender_id = db.upsert_sender(
        conn,
        email=status.email,
        display_name=display_name,
        token_path=status.token_path,
        daily_cap=10,
        status="connected",
    )
    db.set_setting(conn, "sender_email", status.email)
    return sender_id


def campaigns_page(st, conn, config: AppConfig) -> None:
    selected_id = st.session_state.get("campaign_id")
    if selected_id and db.get_campaign(conn, int(selected_id)):
        campaign_editor(st, conn, config, int(selected_id))
        return

    st.title("Campaigns")
    st.caption("Create or open a campaign. Importing recipients, writing the email, previewing, sending tests, autopilot, and logs all happen inside the campaign.")

    top = st.columns([1, 4])
    if top[0].button("+ New campaign", type="primary"):
        campaign_id = db.create_campaign(conn, "Job outreach campaign")
        st.session_state["campaign_id"] = campaign_id
        st.rerun()

    campaigns = db.list_campaigns(conn)
    if not campaigns:
        st.info("No campaigns yet. Create your first campaign.")
        return

    rows = []
    for campaign in campaigns:
        stats = db.campaign_stats(conn, int(campaign["id"]))
        rows.append(
            {
                "Campaign name": campaign["name"],
                "Recipients count": stats["recipients"],
                "Sent": stats["sent"],
                "Opens/tracking status": "OFF",
                "Status": display_campaign_status(str(campaign["status"])),
                "Created date": campaign["created_at"],
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.subheader("Open campaign")
    campaign_by_id = {int(row["id"]): row for row in campaigns}
    campaign_id = st.selectbox(
        "Campaign",
        list(campaign_by_id.keys()),
        format_func=lambda campaign_key: (
            f"{campaign_by_id[campaign_key]['name']} - "
            f"{display_campaign_status(campaign_by_id[campaign_key]['status'])}"
        ),
        label_visibility="collapsed",
    )
    if st.button("Open campaign", type="primary"):
        st.session_state["campaign_id"] = int(campaign_id)
        st.rerun()


def display_campaign_status(status: str) -> str:
    return {"running": "autopilot", "stopped": "ended", "active": "autopilot"}.get(status, status)


def campaign_editor(st, conn, config: AppConfig, campaign_id: int) -> None:
    campaign = db.get_campaign(conn, campaign_id)
    if campaign is None:
        st.session_state.pop("campaign_id", None)
        st.rerun()
        return
    if not campaign["selected_sender_id"] and db.default_sender_id(conn):
        db.set_campaign_sender(conn, campaign_id, db.default_sender_id(conn))
        campaign = db.get_campaign(conn, campaign_id)

    render_campaign_header(st, conn, config, campaign)

    main, right = st.columns([2.2, 1])
    with main:
        composer_section(st, conn, config, campaign)
        campaign_activity_section(st, conn, config, campaign)
    with right:
        right_settings_panel(st, conn, config, campaign)

    if st.session_state.get("show_recipient_modal"):
        recipient_selection_dialog(st, conn, campaign_id)
    if st.session_state.get("show_preview_modal"):
        preview_dialog(st, conn, config, campaign_id)
    if st.session_state.get("show_sender_modal"):
        sender_change_dialog(st, conn, campaign_id)
    if st.session_state.get("show_attachment_modal"):
        attachment_upload_dialog(st, conn, config, campaign_id)
    if st.session_state.get("show_variable_modal"):
        variable_dialog(st, campaign_id)
    if st.session_state.get("show_send_settings_modal"):
        send_settings_dialog(st, conn, config, campaign_id)
    if st.session_state.get("show_send_modal"):
        send_dialog(st, conn, config, campaign)
    if st.session_state.get("show_template_modal"):
        template_dialog(st, campaign_id)
    if st.session_state.get("show_export_logs_modal"):
        export_logs_dialog(st, conn, campaign_id)


def render_campaign_header(st, conn, config: AppConfig, campaign) -> None:
    campaign_id = int(campaign["id"])
    recipient_count = db.campaign_contact_count(conn, campaign_id)
    status = display_campaign_status(str(campaign["status"]))

    header_cols = st.columns([5, 1.6, 1.8, 1.2])
    with header_cols[0]:
        title_cols = st.columns([0.4, 5, 1, 1])
        with title_cols[0]:
            if st.button("←", key="back_to_campaigns"):
                st.session_state.pop("campaign_id", None)
                st.rerun()
        with title_cols[1]:
            name = st.text_input("Campaign name", value=str(campaign["name"]), label_visibility="collapsed", key=f"header_name_field_{campaign_id}")
            if name != campaign["name"]:
                db.update_campaign_name(conn, campaign_id, name)
                st.rerun()
        with title_cols[2]:
            st.markdown(f"<span class='muted-badge' style='margin-top: 4px;'>{status}</span>", unsafe_allow_html=True)
        with title_cols[3]:
            st.markdown(f"<span style='color: #64748b; font-size: 0.95rem; display: inline-block; margin-top: 6px;'>{recipient_count} recipients</span>", unsafe_allow_html=True)
            
    with header_cols[1]:
        if st.button("Show preview", key=f"header_preview_btn_{campaign_id}", use_container_width=True):
            st.session_state["show_preview_modal"] = True
            st.rerun()
            
    with header_cols[2]:
        if st.button("Send emails", type="primary", icon="🚀", key=f"header_send_emails_btn_{campaign_id}", use_container_width=True):
            st.session_state["show_send_modal"] = True
            st.rerun()
            
    with header_cols[3]:
        with st.popover("More", use_container_width=True):
            if st.button("Pause campaign", key=f"more_pause_{campaign_id}", use_container_width=True):
                db.set_campaign_status(conn, "paused", campaign_id)
                st.success("Campaign paused")
                st.rerun()
            if st.button("Stop campaign", key=f"more_stop_{campaign_id}", use_container_width=True):
                db.set_campaign_status(conn, "stopped", campaign_id)
                st.warning("Campaign stopped")
                st.rerun()
            if st.button("Export logs", key=f"more_logs_{campaign_id}", use_container_width=True):
                st.session_state["show_export_logs_modal"] = True
                st.rerun()


def composer_section(st, conn, config: AppConfig, campaign) -> None:
    campaign_id = int(campaign["id"])
    init_composer_state(st, campaign)
    
    with st.container(border=True):
        st.markdown("### Composer")
        from_row(st, conn, campaign_id)
        to_row(st, conn, campaign_id)
        
        # Subject row with Subject label on the left
        cols_sub = st.columns([1, 8])
        with cols_sub[0]:
            st.markdown("<span style='color: #64748b; font-size: 0.95rem; font-weight: 500; display: inline-block; margin-top: 8px;'>Subject</span>", unsafe_allow_html=True)
        with cols_sub[1]:
            st.markdown('<div class="subject-input">', unsafe_allow_html=True)
            subject = st.text_input("Subject", key=f"subject_{campaign_id}", label_visibility="collapsed", placeholder="Enter your email subject")
            st.markdown('</div>', unsafe_allow_html=True)
            
        st.markdown("---")
        
        # Toolbar directly above body
        tb = st.columns([1.8, 1.8, 6.4])
        with tb[0]:
            st.markdown('<div class="toolbar-btn">', unsafe_allow_html=True)
            if st.button("Insert variable", key=f"ins_var_{campaign_id}", use_container_width=True):
                st.session_state["show_variable_modal"] = True
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with tb[1]:
            st.markdown('<div class="toolbar-btn">', unsafe_allow_html=True)
            if st.button("Use template", key=f"use_tpl_{campaign_id}", use_container_width=True):
                st.session_state["show_template_modal"] = True
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="body-textarea">', unsafe_allow_html=True)
        body = st.text_area("Body", key=f"body_{campaign_id}", height=280, label_visibility="collapsed", placeholder="Compose your email or select a template...")
        st.markdown('</div>', unsafe_allow_html=True)
        
        attachment_row(st, conn, config, campaign)

        with st.expander("Advanced email options", expanded=False):
            fallback = st.text_area("Fallback body", key=f"fallback_{campaign_id}", height=180, placeholder="Fallback content if variables are missing...")
            attachment_path = st.text_input("Attachment path", key=f"attachment_path_{campaign_id}")
            raw_template_mode = st.checkbox("Raw template mode", value=False)
            st.caption("Use raw template mode only when editing Jinja variables directly.")
            require_attachment = st.checkbox(
                "Require attachment for this campaign",
                value=db.get_setting(conn, f"campaign_{campaign_id}_require_attachment", "false") == "true",
                key=f"req_att_check_{campaign_id}"
            )

        cols_btn = st.columns([8, 2])
        with cols_btn[1]:
            if st.button("Save draft", type="primary", key=f"save_draft_btn_{campaign_id}", use_container_width=True):
                db.update_campaign(
                    conn,
                    campaign_id,
                    subject,
                    body,
                    fallback,
                    attachment_path,
                )
                db.clear_campaign_previews(conn, campaign_id)
                config.campaign.attachment_path = attachment_path
                save_config(config, config_path())
                db.set_setting(conn, f"campaign_{campaign_id}_template_saved", True)
                db.set_setting(conn, f"campaign_{campaign_id}_test_sent", False)
                db.set_setting(conn, f"campaign_{campaign_id}_require_attachment", "true" if require_attachment else "false")
                st.success("Draft saved successfully")
                st.rerun()


def init_composer_state(st, campaign) -> None:
    campaign_id = int(campaign["id"])
    defaults = {
        f"subject_{campaign_id}": str(campaign["subject_template"]),
        f"body_{campaign_id}": str(campaign["body_template"]),
        f"fallback_{campaign_id}": str(campaign["fallback_body_template"]),
        f"attachment_path_{campaign_id}": str(campaign["attachment_path"] or ""),
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def from_row(st, conn, campaign_id: int) -> None:
    legacy_status = gmail_connection_status()
    if legacy_status.connected and not db.get_sender_by_email(conn, legacy_status.email):
        sender_id = register_connected_sender(conn, legacy_status)
        if not db.get_campaign_sender(conn, campaign_id):
            db.set_campaign_sender(conn, campaign_id, sender_id)

    sender = db.get_campaign_sender(conn, campaign_id)
    cols = st.columns([1, 8])
    with cols[0]:
        st.markdown("<span style='color: #64748b; font-size: 0.95rem; font-weight: 500; display: inline-block; margin-top: 4px;'>From</span>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown('<div class="from-dropdown-btn">', unsafe_allow_html=True)
        if sender:
            status = gmail_connection_status(token_path=sender["token_path"])
            sender_text = f"{sender['display_name'] or 'Default sender'} <{sender['email']}> ▾"
            if st.button(sender_text, key=f"change_sender_{campaign_id}", use_container_width=True):
                st.session_state["show_sender_modal"] = True
                st.rerun()
            if not status.connected:
                st.caption(f"Sender needs reconnect: {status.status}")
        else:
            if st.button("No sender connected ▾", key=f"connect_gmail_{campaign_id}", use_container_width=True):
                if credentials_available():
                    try:
                        connected = connect_and_get_profile(
                            force_reauth=True,
                            token_path=default_token_path(),
                            prompt="select_account consent",
                        )
                        sender_id = register_connected_sender(conn, connected)
                        db.set_campaign_sender(conn, campaign_id, sender_id)
                        st.success(f"Connected sender: {connected.email}")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
                else:
                    st.session_state["show_gmail_setup_modal"] = True
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


def to_row(st, conn, campaign_id: int) -> None:
    recipient_count = db.campaign_contact_count(conn, campaign_id)
    cols = st.columns([1, 8])
    with cols[0]:
        st.markdown("<span style='color: #64748b; font-size: 0.95rem; font-weight: 500; display: inline-block; margin-top: 4px;'>To</span>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown('<div class="to-pill-btn">', unsafe_allow_html=True)
        pill_text = f"{recipient_count} recipient" if recipient_count == 1 else (f"{recipient_count} recipients" if recipient_count else "0 recipients")
        if st.button(pill_text, key=f"to_recipients_{campaign_id}"):
            st.session_state["show_recipient_modal"] = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


def attachment_row(st, conn, config: AppConfig, campaign) -> None:
    campaign_id = int(campaign["id"])
    path = str(campaign["attachment_path"] or config.campaign.attachment_path or "")
    resolved = db.resolve_project_path(path) if path else None
    exists = bool(resolved and resolved.exists())
    filename = Path(path).name if path else ""
    
    cols = st.columns([1, 8])
    with cols[0]:
        st.markdown("<span style='color: #64748b; font-size: 0.95rem; font-weight: 500; display: inline-block; margin-top: 4px;'>File</span>", unsafe_allow_html=True)
    with cols[1]:
        st.markdown('<div class="from-dropdown-btn">', unsafe_allow_html=True)
        pill_text = f"{filename} ▾" if exists else "Add attachment ▾"
        if st.button(pill_text, key=f"change_attachment_{campaign_id}", use_container_width=True):
            st.session_state["show_attachment_modal"] = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)


def gmail_setup_dialog(st, conn) -> None:
    @st.dialog("Gmail setup wizard", width="large")
    def _dialog() -> None:
        st.subheader("Step 1: Create or open Google Cloud project")
        st.write("This is where you register this app with Google. You do this once as the project owner.")
        st.link_button("Open Google Cloud Console", "https://console.cloud.google.com/")

        st.subheader("Step 2: Enable APIs")
        st.write("Enable the APIs this app needs.")
        api_cols = st.columns(2)
        api_cols[0].link_button("Open Gmail API page", "https://console.cloud.google.com/apis/library/gmail.googleapis.com")
        api_cols[1].link_button("Open Google Sheets API page", "https://console.cloud.google.com/apis/library/sheets.googleapis.com")
        st.checkbox("Gmail API enabled", key="wizard_gmail_api_done")
        st.checkbox("Google Sheets API enabled", key="wizard_sheets_api_done")

        st.subheader("Step 3: Create OAuth client")
        st.write("Create an OAuth Client ID for this local app.")
        st.warning("Application type must be: Desktop app. Do not choose Web application for this local app.")
        st.write("Name suggestion: `Job Outreach Sender Desktop`")
        st.link_button("Open OAuth Clients page", "https://console.cloud.google.com/apis/credentials")

        st.subheader("Step 4: Add credentials to the app")
        st.caption("Downloading and uploading the JSON file is recommended. Client ID alone is not enough.")
        upload_tab, paste_tab = st.tabs(["Upload downloaded JSON", "Paste client details"])
        with upload_tab:
            uploaded = st.file_uploader("Upload OAuth Desktop client JSON", type=["json"])
            if uploaded is not None:
                try:
                    data = json.loads(uploaded.getvalue().decode("utf-8"))
                    ok, message = save_credentials_json(data)
                    if ok:
                        st.success(message)
                    else:
                        st.error(message)
                except Exception as exc:
                    st.error(f"Could not read JSON file: {exc}")
        with paste_tab:
            client_id = st.text_input("Client ID")
            client_secret = st.text_input("Client Secret", type="password")
            if st.button("Generate credentials.json"):
                ok, message = save_manual_credentials(client_id, client_secret)
                if ok:
                    st.success(message)
                else:
                    st.error(message)

        st.subheader("OAuth status")
        st.dataframe(pd.DataFrame(wizard_oauth_status_rows()), width="stretch", hide_index=True)
        st.caption(f"Expected path: {credentials_file_path()}")

        st.subheader("Step 5: Connect Gmail")
        connect_cols = st.columns(3)
        if connect_cols[0].button("Check again"):
            st.rerun()
        if connect_cols[1].button("Connect Gmail", type="primary", disabled=not credentials_available()):
            try:
                connected = connect_and_get_profile(
                    force_reauth=True,
                    token_path=default_token_path(),
                    prompt="select_account consent",
                )
                register_connected_sender(conn, connected)
                st.success(f"Connected sender: {connected.email}")
            except Exception as exc:
                st.error(str(exc))
        if connect_cols[2].button("Connect Google Sheets", disabled=not credentials_available()):
            try:
                connect_google_sheets_oauth()
                st.success("Google Sheets connected")
            except Exception as exc:
                st.error(str(exc))

        if st.button("Close"):
            st.session_state["show_gmail_setup_modal"] = False
            st.rerun()

    _dialog()


def sender_change_dialog(st, conn, campaign_id: int) -> None:
    @st.dialog("Change sender", width="large")
    def _dialog() -> None:
        if not credentials_available():
            st.write("No Gmail sender connected.")
            if st.button("Connect Gmail"):
                st.session_state["show_sender_modal"] = False
                st.session_state["show_gmail_setup_modal"] = True
                st.rerun()
            if st.button("Close"):
                st.session_state["show_sender_modal"] = False
                st.rerun()
            return

        senders = db.list_senders(conn)
        if not senders:
            st.write("No Gmail sender connected.")
            if st.button("Connect Gmail", type="primary"):
                try:
                    connected = connect_and_get_profile(
                        force_reauth=True,
                        token_path=default_token_path(),
                        prompt="select_account consent",
                    )
                    sender_id = register_connected_sender(conn, connected)
                    db.set_campaign_sender(conn, campaign_id, sender_id)
                    st.success(f"Connected sender: {connected.email}")
                    st.session_state["show_sender_modal"] = False
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
            if st.button("Close"):
                st.session_state["show_sender_modal"] = False
                st.rerun()
            return

        selected_sender = db.get_campaign_sender(conn, campaign_id)
        sender_by_id = {int(sender["id"]): sender for sender in senders}
        sender_ids = list(sender_by_id.keys())
        selected_id = int(selected_sender["id"]) if selected_sender else sender_ids[0]
        chosen_id = st.selectbox(
            "From",
            sender_ids,
            index=sender_ids.index(selected_id) if selected_id in sender_ids else 0,
            format_func=lambda sender_id: (
                f"{sender_by_id[sender_id]['display_name'] or 'Default sender'} "
                f"<{sender_by_id[sender_id]['email']}>"
            ),
        )
        chosen = sender_by_id[int(chosen_id)]
        status = gmail_connection_status(token_path=chosen["token_path"])
        st.write("Status:", status.status)
        if status.detail:
            st.caption(status.detail)
        actions = st.columns(4)
        if actions[0].button("Use sender", type="primary"):
            db.set_campaign_sender(conn, campaign_id, int(chosen_id))
            st.session_state["show_sender_modal"] = False
            st.rerun()
        if actions[1].button("Connect another Gmail sender"):
            try:
                connected = connect_sender_account(force_reauth=True)
                sender_id = register_connected_sender(conn, connected)
                db.set_campaign_sender(conn, campaign_id, sender_id)
                st.success(f"Connected sender: {connected.email}")
                st.session_state["show_sender_modal"] = False
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if actions[2].button("Reconnect"):
            try:
                connected = connect_and_get_profile(
                    force_reauth=True,
                    token_path=chosen["token_path"],
                    prompt="select_account consent",
                )
                sender_id = db.upsert_sender(
                    conn,
                    email=connected.email,
                    display_name=str(chosen["display_name"] or "Default sender"),
                    token_path=str(chosen["token_path"]),
                    daily_cap=int(chosen["daily_cap"]),
                    status="connected",
                    is_default=bool(chosen["is_default"]),
                )
                db.set_campaign_sender(conn, campaign_id, sender_id)
                st.success(f"Reconnected sender: {connected.email}")
                st.session_state["show_sender_modal"] = False
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if actions[3].button("Default"):
            db.set_default_sender(conn, int(chosen_id))
            st.success("Default sender updated")
        remove_cols = st.columns(2)
        if remove_cols[0].button("Remove sender"):
            db.remove_sender(conn, int(chosen_id))
            st.warning("Sender removed")
            st.session_state["show_sender_modal"] = False
            st.rerun()
        if remove_cols[1].button("Close"):
            st.session_state["show_sender_modal"] = False
            st.rerun()

    _dialog()


def attachment_upload_dialog(st, conn, config: AppConfig, campaign_id: int) -> None:
    @st.dialog("Attachment", width="large")
    def _dialog() -> None:
        campaign = db.get_campaign(conn, campaign_id)
        current_path = str(campaign["attachment_path"] or config.campaign.attachment_path or "")
        resolved = db.resolve_project_path(current_path) if current_path else None
        exists = bool(resolved and resolved.exists())
        if exists:
            st.write(f"Current: {Path(current_path).name}")
        else:
            st.write("No attachment added.")
        uploaded = st.file_uploader("Upload attachment", type=["pdf"])
        raw_path = st.text_input("File path", value=current_path)
        if uploaded:
            upload_dir = ROOT / "data" / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            path = upload_dir / uploaded.name
            path.write_bytes(uploaded.getbuffer())
            raw_path = str(path.relative_to(ROOT))
            st.success(f"Uploaded {uploaded.name}")
        action_cols = st.columns(3)
        if action_cols[0].button("Save", type="primary"):
            db.update_campaign(
                conn,
                campaign_id,
                str(campaign["subject_template"]),
                str(campaign["body_template"]),
                str(campaign["fallback_body_template"]),
                raw_path,
            )
            st.session_state[f"attachment_path_{campaign_id}"] = raw_path
            config.campaign.attachment_path = raw_path
            save_config(config, config_path())
            st.session_state["show_attachment_modal"] = False
            st.rerun()
        if exists and action_cols[1].button("Remove"):
            db.update_campaign(
                conn,
                campaign_id,
                str(campaign["subject_template"]),
                str(campaign["body_template"]),
                str(campaign["fallback_body_template"]),
                "",
            )
            st.session_state[f"attachment_path_{campaign_id}"] = ""
            st.session_state["show_attachment_modal"] = False
            st.rerun()
        if action_cols[2].button("Close"):
            st.session_state["show_attachment_modal"] = False
            st.rerun()

    _dialog()


def variable_dialog(st, campaign_id: int) -> None:
    @st.dialog("Insert variable")
    def _dialog() -> None:
        st.caption("Choose a variable to append to the email body.")
        for variable in VARIABLES:
            if st.button(variable, key=f"variable_modal_{campaign_id}_{variable}"):
                body_key = f"body_{campaign_id}"
                st.session_state[body_key] = f"{st.session_state.get(body_key, '').rstrip()} {variable}"
                st.session_state["show_variable_modal"] = False
                st.rerun()
        if st.button("Close"):
            st.session_state["show_variable_modal"] = False
            st.rerun()

    _dialog()


def send_settings_dialog(st, conn, config: AppConfig, campaign_id: int) -> None:
    @st.dialog("Edit send settings", width="large")
    def _dialog() -> None:
        campaign = db.get_campaign(conn, campaign_id)
        selected_sender = db.get_campaign_sender(conn, campaign_id)
        with st.form(f"send_settings_modal_{campaign_id}"):
            autopilot_enabled = st.checkbox("Autopilot enabled", value=str(campaign["status"]) in {"active", "running"})
            days = st.multiselect(
                "Sending days",
                ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                default=config.sending.days,
            )
            start_time = st.text_input("Start time", value=config.sending.start_time)
            end_time = st.text_input("End time", value=config.sending.end_time)
            daily_cap = st.number_input("Daily cap", min_value=1, value=config.sending.daily_cap)
            sender_daily_cap = st.number_input(
                "Selected sender daily cap",
                min_value=1,
                value=int(selected_sender["daily_cap"]) if selected_sender else 10,
                disabled=selected_sender is None,
            )
            delay_minutes = st.number_input("Delay between emails", min_value=1, value=config.sending.delay_minutes)
            st.checkbox("Track emails", value=False, disabled=True)
            st.checkbox("Unsubscribe link", value=False, disabled=True)
            st.caption("Warmup: Day 1 = 5, Day 2 = 10, Day 3 = 15, Day 4 = 20, Day 5+ = 30/day. Never exceed 50/day unless manually overridden.")
            saved = st.form_submit_button("Save settings", type="primary")
        if saved:
            config.sending.days = days
            config.sending.start_time = start_time
            config.sending.end_time = end_time
            config.sending.daily_cap = int(daily_cap)
            config.sending.delay_minutes = int(delay_minutes)
            save_config(config, config_path())
            if selected_sender:
                db.update_sender_daily_cap(conn, int(selected_sender["id"]), int(sender_daily_cap))
            if autopilot_enabled:
                db.set_campaign_status(conn, "active", campaign_id)
            elif str(campaign["status"]) in {"active", "running"}:
                db.set_campaign_status(conn, "paused", campaign_id)
            st.session_state["show_send_settings_modal"] = False
            st.rerun()
        if st.button("Close"):
            st.session_state["show_send_settings_modal"] = False
            st.rerun()

    _dialog()


def send_dialog(st, conn, config: AppConfig, campaign) -> None:
    @st.dialog("Send campaign", width="large")
    def _dialog() -> None:
        campaign_id = int(campaign["id"])
        sender = db.get_campaign_sender(conn, campaign_id)
        sender_status = (
            gmail_connection_status(token_path=sender["token_path"])
            if sender
            else gmail_connection_status(token_path="tokens/missing.json")
        )
        checklist = campaign_checklist(conn, config, campaign, sender_status)
        missing = [label for label, ok in checklist.items() if not ok]

        block_items = []
        if not checklist.get("Gmail connected", False):
            block_items.append(("Sender missing", "show_sender_modal"))
        if not checklist.get("Recipients selected", False) or not checklist.get("Approved recipients", False):
            block_items.append(("Recipients missing or none approved", "show_recipient_modal"))
        if not checklist.get("Preview generated", False):
            block_items.append(("Preview not generated", "show_preview_modal"))
        if not checklist.get("Test sent", False):
            block_items.append(("Test not sent", "show_preview_modal"))

        if block_items:
            st.error("Cannot send yet:")
            for label, state_key in block_items:
                cols = st.columns([3, 1])
                cols[0].write(f"\u26a0\ufe0f {label}")
                btn_label = {
                    "show_sender_modal": "Connect sender",
                    "show_recipient_modal": "Select recipients",
                    "show_preview_modal": "Preview / Send test"
                }.get(state_key, "Fix")
                if cols[1].button(btn_label, key=f"send_fix_{state_key}_{label.replace(' ', '_').replace('/', '_').lower()}"):
                    st.session_state["show_send_modal"] = False
                    st.session_state[state_key] = True
                    st.rerun()
            if st.button("Close", key="send_modal_close_blocks"):
                st.session_state["show_send_modal"] = False
                st.rerun()
            return

        default_tab = st.session_state.pop("send_mode_tab", "Send now")
        tab_index = ["Send now", "Schedule", "Autopilot"].index(default_tab) if default_tab in ["Send now", "Schedule", "Autopilot"] else 0

        mode = st.radio("Send mode", ["Send now", "Schedule", "Autopilot"], index=tab_index, horizontal=True)

        if mode == "Send now":
            recipient_count = db.campaign_contact_count(conn, campaign_id)
            st.write(f"This will start sending to **{recipient_count} approved recipients** now.")
            st.info("Sending respects all daily caps, warmup limits, and delays. Emails are not sent all at once.")
            
            daily_cap = st.number_input("Campaign daily cap", min_value=1, value=config.sending.daily_cap)
            delay = st.number_input("Delay between emails (minutes)", min_value=1, value=config.sending.delay_minutes)
            
            cols = st.columns(2)
            if cols[0].button("Start sending", type="primary", key="send_now_confirm"):
                config.sending.daily_cap = int(daily_cap)
                config.sending.delay_minutes = int(delay)
                save_config(config, config_path())
                db.set_campaign_status(conn, "sending", campaign_id)
                start_background_autopilot(database_path(), config_path())
                st.success("Sending campaign now...")
                st.session_state["show_send_modal"] = False
                st.rerun()
            if cols[1].button("Cancel", key="send_now_cancel"):
                st.session_state["show_send_modal"] = False
                st.rerun()

        elif mode == "Schedule":
            from datetime import date as date_type
            start_date = st.date_input("Start date", value=date_type.today())
            start_time = st.text_input("Start time", value=config.sending.start_time)
            days = st.multiselect(
                "Sending days",
                ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                default=config.sending.days,
            )
            end_time = st.text_input("End time (time window)", value=config.sending.end_time)
            daily_cap = st.number_input("Daily cap", min_value=1, value=config.sending.daily_cap)
            delay = st.number_input("Delay between emails (minutes)", min_value=1, value=config.sending.delay_minutes)
                
            cols = st.columns(2)
            if cols[0].button("Confirm Schedule", type="primary", key="send_schedule_confirm"):
                config.sending.days = days
                config.sending.start_time = start_time
                config.sending.end_time = end_time
                config.sending.daily_cap = int(daily_cap)
                config.sending.delay_minutes = int(delay)
                save_config(config, config_path())
                db.set_campaign_status(conn, "scheduled", campaign_id)
                st.success("Campaign scheduled!")
                st.session_state["show_send_modal"] = False
                st.rerun()
            if cols[1].button("Cancel", key="send_sched_cancel"):
                st.session_state["show_send_modal"] = False
                st.rerun()

        elif mode == "Autopilot":
            days_short = ", ".join(d[:3].title() for d in config.sending.days)
            st.write("Autopilot runs in the background, automatically managing warmup and sending limits.")
            st.caption(f"Current limits: Daily cap: {config.sending.daily_cap} \u00b7 Delay: {config.sending.delay_minutes} min")
            st.caption(f"Warmup Schedule: Day 1=5, Day 2=10, Day 3=15, Day 4=20, Day 5+=30/day")
            
            daily_cap = st.number_input("Autopilot daily cap max", min_value=1, value=config.sending.daily_cap)
            delay = st.number_input("Delay (minutes)", min_value=1, value=config.sending.delay_minutes)
            days = st.multiselect(
                "Sending days",
                ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                default=config.sending.days,
            )
                
            cols = st.columns(2)
            if cols[0].button("Start Autopilot", type="primary", key="send_autopilot_confirm"):
                config.sending.days = days
                config.sending.daily_cap = int(daily_cap)
                config.sending.delay_minutes = int(delay)
                save_config(config, config_path())
                db.set_campaign_status(conn, "active", campaign_id)
                start_background_autopilot(database_path(), config_path())
                st.success("Autopilot started!")
                st.session_state["show_send_modal"] = False
                st.rerun()
            if cols[1].button("Cancel", key="send_ap_cancel"):
                st.session_state["show_send_modal"] = False
                st.rerun()

    _dialog()


def template_dialog(st, campaign_id: int) -> None:
    @st.dialog("Use template", width="large")
    def _dialog() -> None:
        st.caption("Select a template to populate the subject and body. This will overwrite your current draft.")
        
        templates = [
            {
                "name": "Standard Student Outreach (Default)",
                "subject": DEFAULT_SUBJECT_TEMPLATE,
                "body": DEFAULT_BODY_TEMPLATE,
                "fallback": DEFAULT_FALLBACK_BODY_TEMPLATE,
            },
            {
                "name": "Direct Referral Request",
                "subject": "Quick question regarding your team at {{ Company_Name }}",
                "body": "Hi {{ First_Name }},\n\nI was browsing your team profiles at {{ Company_Name }} and thought my background in AI/Computer Science might align with any junior developer positions.\n\nAre you open to a brief chat or referral?\n\nBest regards,\nYour Name",
                "fallback": "Hi {{ First_Name }},\n\nHope you are well. Are you currently hiring junior technical roles at {{ Company_Name }}?\n\nBest regards,\nYour Name",
            }
        ]

        for i, t in enumerate(templates):
            with st.container(border=True):
                st.markdown(f"**{t['name']}**")
                st.write(f"Subject: `{t['subject']}`")
                if st.button("Apply Template", key=f"apply_tpl_{i}_{campaign_id}"):
                    st.session_state[f"subject_{campaign_id}"] = t["subject"]
                    st.session_state[f"body_{campaign_id}"] = t["body"]
                    st.session_state[f"fallback_{campaign_id}"] = t["fallback"]
                    st.session_state["show_template_modal"] = False
                    st.success("Template applied! Make sure to save your draft.")
                    st.rerun()

        if st.button("Close", key="tpl_close"):
            st.session_state["show_template_modal"] = False
            st.rerun()

    _dialog()


def export_logs_dialog(st, conn, campaign_id: int) -> None:
    @st.dialog("Export logs")
    def _dialog() -> None:
        log = send_log_dataframe(conn, campaign_id=campaign_id)
        if log.empty:
            st.info("No logs for this campaign yet.")
        else:
            st.write(f"Export send log with {len(log)} attempts.")
            st.download_button(
                "Download Send Log (CSV)",
                log.to_csv(index=False).encode("utf-8"),
                f"campaign_{campaign_id}_send_log.csv",
                "text/csv",
                use_container_width=True
            )
        if st.button("Close", key="export_logs_close"):
            st.session_state["show_export_logs_modal"] = False
            st.rerun()

    _dialog()


def campaign_tabs(st, conn, config: AppConfig, campaign) -> None:
    recipients_tab, preview_tab, logs_tab = st.tabs(["Recipients", "Preview", "Logs"])
    with recipients_tab:
        recipients_section(st, conn, int(campaign["id"]))
    with preview_tab:
        preview_inline_section(st, conn, int(campaign["id"]))
    with logs_tab:
        logs_section(st, conn, int(campaign["id"]))


def campaign_activity_section(st, conn, config: AppConfig, campaign) -> None:
    with st.expander("Campaign activity", expanded=False):
        campaign_tabs(st, conn, config, campaign)


def recipients_section(st, conn, campaign_id: int) -> None:
    rows = db.contact_rows_with_last_log(conn, campaign_id=campaign_id)
    if not rows:
        st.info("No recipients selected yet. Click Select recipients.")
        if st.button("Select recipients now", key="select_recipients_empty"):
            st.session_state["show_recipient_modal"] = True
        return

    table = pd.DataFrame(
        [
            {
                "Email": row["email"],
                "First Name": row["first_name"],
                "Company": row["company_name"],
                "Status": row["status"],
                "Last sent": row["last_sent_at"],
                "Error": row["last_error_message"],
            }
            for row in rows
        ]
    )
    st.dataframe(table, use_container_width=True, hide_index=True)

    row_by_id = {int(row["id"]): row for row in rows}
    selected_id = st.selectbox(
        "Recipient actions",
        list(row_by_id.keys()),
        format_func=lambda contact_id: (
            f"{row_by_id[contact_id]['status']} - "
            f"{row_by_id[contact_id]['email']} - "
            f"{row_by_id[contact_id]['company_name']}"
        ),
    )
    selected = row_by_id[int(selected_id)]
    action_cols = st.columns(6)
    if action_cols[0].button("approve"):
        generate_preview(conn, int(selected_id), campaign_id=campaign_id, mark=True)
        approve_contacts(conn, [int(selected_id)])
        st.rerun()
    if action_cols[1].button("reject"):
        reject_contacts(conn, [int(selected_id)])
        st.rerun()
    if action_cols[2].button("mark replied"):
        db.set_contact_status(conn, int(selected_id), ContactStatus.REPLIED.value)
        st.rerun()
    if action_cols[3].button("mark bounced"):
        db.set_contact_status(conn, int(selected_id), ContactStatus.BOUNCED.value)
        st.rerun()
    if action_cols[4].button("mark do_not_contact"):
        add_email(conn, str(selected["email"]), "Manual DNC")
        st.rerun()
    if action_cols[5].button("reset to approved"):
        db.set_contact_status(conn, int(selected_id), ContactStatus.APPROVED.value)
        st.rerun()

    if st.button("Approve all pending recipients"):
        pending = [int(row["id"]) for row in rows if row["status"] == ContactStatus.PENDING.value]
        for contact_id in pending:
            generate_preview(conn, contact_id, campaign_id=campaign_id, mark=True)
        approved = approve_contacts(conn, pending)
        st.success(f"Approved {approved} recipients")
        st.rerun()


def preview_inline_section(st, conn, campaign_id: int) -> None:
    contacts = db.campaign_contacts(conn, campaign_id, limit=5)
    if not contacts:
        st.info("Select recipients first. Preview becomes available immediately after recipients are selected.")
        return
    if st.button("Open large preview", type="primary"):
        st.session_state["show_preview_modal"] = True
    for contact in contacts:
        item = generate_preview(conn, int(contact["id"]), campaign_id=campaign_id, mark=False)
        with st.expander(f"{item.recipient_email} - {item.subject}"):
            st.text(item.body)


def logs_section(st, conn, campaign_id: int) -> None:
    log = send_log_dataframe(conn, campaign_id=campaign_id)
    if log.empty:
        st.info("No logs for this campaign yet.")
        return
    st.dataframe(log, use_container_width=True, hide_index=True)
    st.download_button(
        "Export send log CSV",
        log.to_csv(index=False).encode("utf-8"),
        f"campaign_{campaign_id}_send_log.csv",
        "text/csv",
    )


def right_settings_panel(st, conn, config: AppConfig, campaign) -> None:
    campaign_id = int(campaign["id"])

    with st.container(border=True):
        st.markdown("### Settings")
        
        # Schedule send row
        st.markdown("📅 **Schedule send**")
        st.caption("Set start date, days and hours window")
        if st.button("Configure Schedule", key=f"sched_config_btn_{campaign_id}", use_container_width=True):
            st.session_state["show_send_modal"] = True
            st.session_state["send_mode_tab"] = "Schedule"
            st.rerun()
            
        st.markdown("---")
        
        # Autopilot row
        st.markdown("🎛️ **Autopilot**")
        st.caption("Auto-throttle daily caps and warmup limits")
        if st.button("Configure Autopilot", key=f"ap_config_btn_{campaign_id}", use_container_width=True):
            st.session_state["show_send_modal"] = True
            st.session_state["send_mode_tab"] = "Autopilot"
            st.rerun()

        st.markdown("---")

        # Track emails row with toggle
        track_emails = st.toggle("Track emails", value=config.campaign.tracking_enabled, key=f"track_emails_toggle_{campaign_id}", help="Track open rates and link clicks")
        if track_emails != config.campaign.tracking_enabled:
            config.campaign.tracking_enabled = track_emails
            save_config(config, config_path())
            st.rerun()

        # Unsubscribe link row with toggle
        unsubscribe_link = st.toggle("Unsubscribe link", value=config.campaign.followups_enabled, key=f"unsub_link_toggle_{campaign_id}", help="Append opt-out footer link to emails")
        if unsubscribe_link != config.campaign.followups_enabled:
            config.campaign.followups_enabled = unsubscribe_link
            save_config(config, config_path())
            st.rerun()




def recipient_selection_dialog(st, conn, campaign_id: int) -> None:
    @st.dialog("Select recipients", width="large")
    def _dialog() -> None:
        tabs = st.tabs(["Google Sheets", "Import CSV", "Contact list", "Copy / paste"])
        with tabs[0]:
            google_sheets_recipient_tab(st, conn, campaign_id)
        with tabs[1]:
            csv_recipient_tab(st, conn, campaign_id)
        with tabs[2]:
            contact_list_recipient_tab(st, conn, campaign_id)
        with tabs[3]:
            copy_paste_recipient_tab(st, conn, campaign_id)
        if st.button("Close"):
            st.session_state["show_recipient_modal"] = False
            st.rerun()

    _dialog()


def google_sheets_recipient_tab(st, conn, campaign_id: int) -> None:
    sheets_status = sheets_connection_status()
    st.write(f"Google Sheets OAuth: {sheets_status.status}")
    if not credentials_available():
        st.info("Public or published CSV links can be used without OAuth. Private Google Sheets require the setup wizard.")
        if st.button("Open setup wizard", key="open_sheets_setup_wizard"):
            st.session_state["show_recipient_modal"] = False
            st.session_state["show_gmail_setup_modal"] = True
            st.rerun()
    elif not sheets_status.connected:
        st.info("Public or published CSV links can be used without OAuth. Private Google Sheets require connecting Google Sheets.")
        if st.button("Connect Google Sheets", key="connect_sheets_recipient_top"):
            try:
                connect_google_sheets_oauth()
                st.success("Google Sheets connected")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    sheet_url = st.text_input("Google Sheet URL", key="recipient_sheet_url")
    header_row = st.number_input("Header row", min_value=1, max_value=50, value=1, key="recipient_sheet_header")
    c1, c2, c3 = st.columns(3)
    if c1.button("Fetch sheets", disabled=not sheet_url):
        try:
            sheet = parse_google_sheet_url_details(sheet_url)
            tabs = list_sheet_tabs(sheet.sheet_id)
            st.session_state["recipient_sheet_tabs"] = tabs
            st.session_state["recipient_sheet_id"] = sheet.sheet_id
            st.success(f"Fetched {len(tabs)} tabs")
        except Exception as exc:
            st.error(str(exc))
    if c2.button("Connect Google Sheets", disabled=not credentials_available()):
        try:
            connect_google_sheets_oauth()
            st.success("Google Sheets connected")
        except Exception as exc:
            st.error(str(exc))
    tabs = st.session_state.get("recipient_sheet_tabs", [])
    selected_tab = st.selectbox("Select sheet/tab", [tab["title"] for tab in tabs]) if tabs else ""
    use_private = st.checkbox("Use private Sheets API", value=bool(tabs))
    if c3.button("Preview rows", disabled=not sheet_url):
        try:
            frame, meta = load_sheet_for_recipients(sheet_url, selected_tab, header_row, use_private)
            st.session_state["recipient_sheet_frame"] = frame
            st.session_state["recipient_sheet_meta"] = meta
            st.success(f"Loaded {len(frame)} rows")
        except Exception as exc:
            st.error(str(exc))

    frame = st.session_state.get("recipient_sheet_frame")
    if frame is None:
        return
    st.dataframe(frame.head(10), use_container_width=True)
    mapping = mapping_ui(st, frame, "sheet_recipients")
    if st.button("Use this sheet", type="primary"):
        result, attached = import_and_attach_frame(
            conn,
            campaign_id,
            frame,
            mapping,
            source_type="google_sheet",
            source_url=sheet_url,
            sheet_id=st.session_state.get("recipient_sheet_meta", {}).get("sheet_id", ""),
            sheet_name=selected_tab or st.session_state.get("recipient_sheet_meta", {}).get("sheet_name", ""),
        )
        st.success(f"Recipients selected: {db.campaign_contact_count(conn, campaign_id)} total. Imported {result.imported}, attached {attached}.")


def load_sheet_for_recipients(sheet_url: str, tab_name: str, header_row: int, use_private: bool) -> tuple[pd.DataFrame, dict[str, str]]:
    if "output=csv" in sheet_url or "/pub?" in sheet_url or "format=csv" in sheet_url:
        return get_published_csv(sheet_url, header_row=header_row), {"sheet_id": "", "sheet_name": ""}
    sheet = parse_google_sheet_url_details(sheet_url)
    if use_private and tab_name:
        return read_sheet_rows(sheet.sheet_id, tab_name, header_row=header_row), {"sheet_id": sheet.sheet_id, "sheet_name": tab_name}
    return get_public_sheet_csv(sheet.sheet_id, gid=sheet.gid, header_row=header_row), {"sheet_id": sheet.sheet_id, "sheet_name": tab_name or sheet.gid or ""}


def csv_recipient_tab(st, conn, campaign_id: int) -> None:
    uploaded = st.file_uploader("Upload CSV", type=["csv"], key="recipient_csv_upload")
    if not uploaded:
        return
    frame = pd.read_csv(uploaded)
    st.write("Detected columns")
    st.json(detect_columns(list(frame.columns)))
    st.dataframe(frame.head(10), use_container_width=True)
    mapping = mapping_ui(st, frame, "csv_recipients")
    if st.button("Use this CSV", type="primary"):
        result, attached = import_and_attach_frame(conn, campaign_id, frame, mapping, source_type="csv")
        st.success(f"Recipients selected: {db.campaign_contact_count(conn, campaign_id)} total. Imported {result.imported}, attached {attached}.")


def contact_list_recipient_tab(st, conn, campaign_id: int) -> None:
    status_filter = st.selectbox("Filter by status", ["all"] + [status.value for status in ContactStatus])
    statuses = None if status_filter == "all" else (status_filter,)
    contacts = db.fetch_contacts(conn, statuses=statuses, limit=2000)
    contact_by_id = {int(row["id"]): row for row in contacts}
    selected_ids = st.multiselect(
        "Select contacts",
        list(contact_by_id.keys()),
        format_func=lambda contact_id: (
            f"{contact_by_id[contact_id]['status']} - "
            f"{contact_by_id[contact_id]['email']} - "
            f"{contact_by_id[contact_id]['company_name']}"
        ),
    )
    if st.button("Use selected contacts", type="primary"):
        attached = db.add_campaign_recipients(conn, campaign_id, selected_ids)
        st.success(f"Attached {attached} contacts. Campaign now has {db.campaign_contact_count(conn, campaign_id)} recipients.")


def copy_paste_recipient_tab(st, conn, campaign_id: int) -> None:
    raw = st.text_area("Paste raw emails or CSV-like text", height=180)
    if not raw:
        return
    frame = parse_pasted_contacts(raw)
    st.write(f"Parsed {len(frame)} possible contacts")
    st.dataframe(frame.head(20), use_container_width=True)
    mapping = detect_columns(list(frame.columns))
    if st.button("Use parsed contacts", type="primary"):
        result, attached = import_and_attach_frame(conn, campaign_id, frame, mapping, source_type="paste")
        st.success(f"Recipients selected: {db.campaign_contact_count(conn, campaign_id)} total. Imported {result.imported}, attached {attached}.")


def parse_pasted_contacts(raw: str) -> pd.DataFrame:
    rows = []
    email_pattern = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
    for line in raw.splitlines():
        email_match = email_pattern.search(line)
        if not email_match:
            continue
        email = normalize_email(email_match.group(0))
        parts = [part.strip() for part in re.split(r"[,;\t]", line) if part.strip()]
        first_name = ""
        company = "Unknown"
        if parts and "@" not in parts[0]:
            first_name = parts[0].split()[0]
        else:
            first_name = email.split("@")[0].split(".")[0].title()
        if len(parts) >= 3:
            company = parts[2]
        rows.append({"Email": email, "First Name": first_name, "Company Name": company, "Keywords": ""})
    return pd.DataFrame(rows, columns=["Email", "First Name", "Company Name", "Keywords"])


def mapping_ui(st, frame: pd.DataFrame, key_prefix: str) -> dict[str, str]:
    st.write("Column mapping")
    detected = detect_columns(list(frame.columns))
    options = ["-- not mapped --"] + list(frame.columns)
    mapping: dict[str, str] = {}
    cols = st.columns(2)
    for index, (field, label, required) in enumerate(MAPPING_FIELDS):
        default = detected.get(field, "-- not mapped --")
        selected = cols[index % 2].selectbox(
            f"{label}{' *' if required else ''}",
            options,
            index=options.index(default) if default in options else 0,
            key=f"{key_prefix}_{field}",
        )
        if selected != "-- not mapped --":
            mapping[field] = selected
    missing = [label for field, label, required in MAPPING_FIELDS if required and field not in mapping]
    if missing:
        st.warning("Missing required mapping: " + ", ".join(missing))
    return mapping


def import_and_attach_frame(
    conn,
    campaign_id: int,
    frame: pd.DataFrame,
    mapping: dict[str, str],
    source_type: str,
    source_url: str = "",
    sheet_id: str = "",
    sheet_name: str = "",
):
    result = import_dataframe(
        frame,
        conn,
        column_mapping=mapping,
        source_type=source_type,
        source_url=source_url,
        sheet_id=sheet_id,
        sheet_name=sheet_name,
    )
    emails = frame_emails(frame, mapping)
    attached = db.add_campaign_recipients_by_emails(conn, campaign_id, emails)
    return result, attached


def frame_emails(frame: pd.DataFrame, mapping: dict[str, str]) -> list[str]:
    email_column = mapping.get("email")
    if not email_column or email_column not in frame.columns:
        return []
    return [normalize_email(value) for value in frame[email_column].tolist() if normalize_email(value)]


def preview_dialog(st, conn, config: AppConfig, campaign_id: int) -> None:
    @st.dialog("Preview emails", width="large")
    def _dialog() -> None:
        contacts = db.campaign_contacts(conn, campaign_id)
        if not contacts:
            st.info("No recipients selected yet.")
            if st.button("Close"):
                st.session_state["show_preview_modal"] = False
                st.rerun()
            return
        index_key = f"preview_index_{campaign_id}"
        if index_key not in st.session_state:
            st.session_state[index_key] = 0
        current_index = max(0, min(int(st.session_state[index_key]), len(contacts) - 1))
        contact = contacts[current_index]
        item = generate_preview(conn, int(contact["id"]), campaign_id=campaign_id, mark=True)

        st.write(f"{current_index + 1} of {len(contacts)}")
        nav = st.columns([1, 1, 4])
        if nav[0].button("Previous", disabled=current_index == 0):
            st.session_state[index_key] = current_index - 1
            st.rerun()
        if nav[1].button("Next", disabled=current_index >= len(contacts) - 1):
            st.session_state[index_key] = current_index + 1
            st.rerun()

        st.write("Recipient:", item.recipient_email)
        st.write("Subject:", item.subject)
        st.text_area("Body", item.body, height=360)
        attachment = str(db.get_campaign(conn, campaign_id)["attachment_path"] or config.campaign.attachment_path)
        st.write("Attachment:", Path(attachment).name if attachment else "No attachment")

        test_to = st.text_input("Test recipient email", value=db.get_setting(conn, f"campaign_{campaign_id}_test_to", ""))
        if st.button("Send test email", type="primary", disabled=not test_to):
            ok, message = send_test_email(
                conn,
                int(contact["id"]),
                test_to,
                config,
                campaign_id=campaign_id,
            )
            if ok:
                db.set_setting(conn, f"campaign_{campaign_id}_test_to", test_to)
                db.set_setting(conn, f"campaign_{campaign_id}_test_sent", True)
                st.success(message)
            else:
                st.error(message)
        if st.button("Close preview"):
            st.session_state["show_preview_modal"] = False
            st.rerun()

    _dialog()


def templates_page(st, conn) -> None:
    st.title("Templates")
    st.caption("Reusable campaign templates. Normal editing still happens inside each campaign composer.")
    campaign = db.get_default_campaign(conn)
    st.text_input("Default subject", value=str(campaign["subject_template"]), disabled=True)
    st.text_area("Default body", value=str(campaign["body_template"]), height=260, disabled=True)
    st.info("Create or open a campaign to edit the active email.")


def contacts_page(st, conn) -> None:
    st.title("Contacts")
    rows = db.contact_rows_with_last_log(conn)
    if not rows:
        st.info("No contacts imported yet. Open a campaign and select recipients.")
        return
    table = pd.DataFrame(
        [
            {
                "Email": row["email"],
                "First Name": row["first_name"],
                "Company": row["company_name"],
                "Status": row["status"],
                "Source": row["source_type"],
                "Last sent": row["last_sent_at"],
                "Error": row["last_error_message"],
            }
            for row in rows
        ]
    )
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.subheader("Do-not-contact")
    c1, c2 = st.columns(2)
    dnc_email = c1.text_input("Add email")
    reason = c2.text_input("Reason", value="Manual DNC")
    if st.button("Add to DNC"):
        st.success(f"Added: {add_email(conn, dnc_email, reason)}")
    uploaded = st.file_uploader("Import DNC CSV", type=["csv"])
    if uploaded and st.button("Import DNC"):
        st.success(f"Imported {import_dnc_csv(conn, uploaded)} emails")
    dnc = [dict(row) for row in dnc_rows(conn)]
    if dnc:
        st.dataframe(pd.DataFrame(dnc), use_container_width=True, hide_index=True)


def analytics_page(st, conn, config: AppConfig) -> None:
    st.title("Analytics")
    campaigns = db.list_campaigns(conn)
    cols = st.columns(5)
    cols[0].metric("Campaigns", len(campaigns))
    cols[1].metric("Contacts", db.count_contacts_by_status(conn)["total"])
    cols[2].metric("Sent today", sent_today_local(conn, config))
    cols[3].metric("Effective cap", effective_daily_cap(conn, config))
    cols[4].metric("Remaining", max(effective_daily_cap(conn, config) - sent_today_local(conn, config), 0))
    rows = []
    for campaign in campaigns:
        stats = db.campaign_stats(conn, int(campaign["id"]))
        rows.append(
            {
                "Campaign": campaign["name"],
                "Recipients": stats["recipients"],
                "Sent": stats["sent"],
                "Status": display_campaign_status(campaign["status"]),
                "Created": campaign["created_at"],
            }
        )
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def settings_page(st, conn, config: AppConfig) -> None:
    st.title("Settings")
    st.caption("Advanced global defaults. Campaign actions live inside the campaign editor.")

    with st.form("settings_form"):
        timezone = st.text_input("Timezone default", value=config.timezone)
        max_cap = st.number_input(
            "Global maximum allowed daily cap",
            min_value=1,
            value=config.sending.max_daily_cap_allowed_without_manual_override,
            help="This is a safety ceiling. Campaigns and senders can use lower daily caps, but cannot exceed this value.",
        )
        bounce_threshold = st.number_input(
            "Global bounce threshold default (%)",
            min_value=0.0,
            value=float(config.sending.bounce_rate_pause_threshold),
        )
        max_errors = st.number_input(
            "Global max errors before pause",
            min_value=1,
            value=config.sending.max_consecutive_errors,
        )
        st.text_input("Database path", value=str(database_path()), disabled=True)
        st.text_input("Config path", value=str(config_path()), disabled=True)
        if st.form_submit_button("Save settings", type="primary"):
            config.timezone = timezone
            config.sending.max_daily_cap_allowed_without_manual_override = int(max_cap)
            config.sending.bounce_rate_pause_threshold = float(bounce_threshold)
            config.sending.max_consecutive_errors = int(max_errors)
            save_config(config, config_path())
            st.success("Settings saved")

    with st.expander("Developer OAuth setup", expanded=False):
        developer_oauth_section(st, conn)


def developer_oauth_section(st, conn) -> None:
    st.caption("OAuth credentials and API status for this local app.")
    gmail_credentials = credentials_file_path()
    gmail_default_token = default_token_path()
    sheets_credentials, sheets_token = sheets_credentials_paths()
    default_gmail = gmail_connection_status()
    sheets_status = sheets_connection_status()

    rows = [
        {"Item": "credentials.json", "Status": "found" if gmail_credentials.exists() else "missing"},
        {"Item": "OAuth client type", "Status": oauth_client_type()},
        {"Item": "Gmail API", "Status": "connected" if default_gmail.connected else "not connected"},
        {"Item": "Google Sheets API", "Status": "connected" if sheets_status.connected else "not connected"},
        {"Item": "Gmail token", "Status": "found" if gmail_default_token.exists() else "missing"},
        {"Item": "Sheets token", "Status": "found" if sheets_token.exists() else "missing"},
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    link_cols = st.columns(2)
    link_cols[0].link_button("Open Gmail API page", "https://console.cloud.google.com/apis/library/gmail.googleapis.com")
    link_cols[1].link_button("Open Google Sheets API page", "https://console.cloud.google.com/apis/library/sheets.googleapis.com")
    link_cols2 = st.columns(2)
    link_cols2[0].link_button("Open OAuth scopes page", "https://console.cloud.google.com/apis/credentials/consent")
    if link_cols2[1].button("Open Gmail setup wizard", key="dev_oauth_open_wizard"):
        st.session_state["show_gmail_setup_modal"] = True
        st.rerun()

    senders = db.list_senders(conn)
    if senders:
        st.write("Connected senders")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Email": sender["email"],
                        "Display name": sender["display_name"],
                        "Status": sender["status"],
                        "Daily cap": sender["daily_cap"],
                        "Default": bool(sender["is_default"]),
                    }
                    for sender in senders
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit(run_cli(sys.argv[1:]))
    run_streamlit()
