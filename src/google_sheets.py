from __future__ import annotations

import os
import re
from io import StringIO
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

import pandas as pd
import requests
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from . import db
from .importer import detect_columns, import_dataframe
from .models import ImportResult

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


@dataclass(frozen=True)
class SheetUrl:
    sheet_id: str
    gid: str | None = None


@dataclass(frozen=True)
class GoogleSheetsConnectionStatus:
    connected: bool
    status: str
    detail: str = ""
    token_path: str = ""


def parse_google_sheet_url(url: str) -> str:
    parsed = parse_google_sheet_url_details(url)
    return parsed.sheet_id


def parse_google_sheet_url_details(url: str) -> SheetUrl:
    text = url.strip()
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", text)
    if match:
        parsed = urlparse(text)
        query = parse_qs(parsed.query)
        gid = query.get("gid", [None])[0]
        if gid is None and "gid=" in parsed.fragment:
            gid = parse_qs(parsed.fragment).get("gid", [None])[0]
        return SheetUrl(match.group(1), gid)

    parsed = urlparse(text)
    query = parse_qs(parsed.query)
    sheet_id = query.get("id", [None])[0]
    gid = query.get("gid", [None])[0]
    if sheet_id:
        return SheetUrl(sheet_id, gid)
    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", text):
        return SheetUrl(text)
    raise ValueError("Could not find a Google Sheet ID in the URL")


def get_public_sheet_csv(sheet_id: str, gid: str | None = None, header_row: int = 1) -> pd.DataFrame:
    params = f"&gid={gid}" if gid else ""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv{params}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text), header=max(header_row - 1, 0))


def get_published_csv(url: str, header_row: int = 1) -> pd.DataFrame:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text), header=max(header_row - 1, 0))


def sheets_credentials_paths() -> tuple[Path, Path]:
    load_dotenv()
    credentials_path = db.resolve_project_path(os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "credentials.json"))
    token_path = db.resolve_project_path(os.getenv("GOOGLE_SHEETS_TOKEN_PATH", "sheets_token.json"))
    return credentials_path, token_path


def sheets_connection_status() -> GoogleSheetsConnectionStatus:
    _, token_path = sheets_credentials_paths()
    if not token_path.exists():
        return GoogleSheetsConnectionStatus(
            False,
            "Token missing",
            detail=f"Missing {token_path}",
            token_path=str(token_path),
        )
    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    except Exception as exc:
        return GoogleSheetsConnectionStatus(False, "Token invalid", detail=str(exc), token_path=str(token_path))
    if creds.expired and not creds.refresh_token:
        return GoogleSheetsConnectionStatus(
            False,
            "Token expired",
            detail="Reconnect Google Sheets to refresh the token.",
            token_path=str(token_path),
        )
    if not creds.valid:
        try:
            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
        except Exception as exc:
            return GoogleSheetsConnectionStatus(False, "Token expired", detail=str(exc), token_path=str(token_path))
    return GoogleSheetsConnectionStatus(True, "Connected", token_path=str(token_path))


def connect_google_sheets_oauth():
    credentials_path, token_path = sheets_credentials_paths()
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(f"Google Sheets OAuth credentials not found at {credentials_path}")
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0, prompt="select_account consent")
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("sheets", "v4", credentials=creds)


def list_sheet_tabs(sheet_id: str, service=None) -> list[dict[str, Any]]:
    sheets = service or connect_google_sheets_oauth()
    metadata = sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
    tabs = []
    for sheet in metadata.get("sheets", []):
        props = sheet.get("properties", {})
        tabs.append({"title": props.get("title", ""), "sheet_id": props.get("sheetId")})
    return tabs


def read_sheet_rows(sheet_id: str, tab_name: str, header_row: int = 1, service=None) -> pd.DataFrame:
    sheets = service or connect_google_sheets_oauth()
    escaped_tab = tab_name.replace("'", "''")
    result = (
        sheets.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=f"'{escaped_tab}'")
        .execute()
    )
    values = result.get("values", [])
    if not values:
        return pd.DataFrame()
    zero_based = max(header_row - 1, 0)
    header = values[zero_based]
    rows = values[zero_based + 1 :]
    return pd.DataFrame(rows, columns=header)


def dataframe_with_header_row(frame: pd.DataFrame, header_row: int) -> pd.DataFrame:
    if frame.empty:
        return frame
    zero_based = max(header_row - 1, 0)
    header = [str(value).strip() for value in frame.iloc[zero_based].tolist()]
    rows = frame.iloc[zero_based + 1 :].reset_index(drop=True)
    rows.columns = header
    return rows


def sync_sheet_to_contacts(
    conn,
    sheet_id: str,
    tab_name: str,
    column_mapping: dict[str, str],
    frame: pd.DataFrame | None = None,
    source_url: str = "",
) -> ImportResult:
    data = frame if frame is not None else read_sheet_rows(sheet_id, tab_name)
    if not column_mapping:
        column_mapping = detect_columns(list(data.columns))
    return import_dataframe(
        data,
        conn,
        column_mapping=column_mapping,
        source_type="google_sheet",
        source_url=source_url,
        sheet_id=sheet_id,
        sheet_name=tab_name,
    )


def write_back_status_to_sheet(*_args, **_kwargs) -> None:
    raise NotImplementedError("Writing statuses back to Google Sheets is reserved for a later version.")
