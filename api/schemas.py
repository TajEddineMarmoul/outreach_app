from __future__ import annotations

from typing import Optional, List, Dict

from pydantic import BaseModel


class CampaignCreate(BaseModel):
    name: str


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    fallback_body_template: Optional[str] = None
    attachment_path: Optional[str] = None
    require_attachment: Optional[bool] = None
    tracking_enabled: Optional[bool] = None
    unsubscribe_link: Optional[bool] = None


class ComposerUpdate(BaseModel):
    subject_template: str
    body_template: str
    fallback_body_template: str
    require_attachment: Optional[bool] = False


class SendSettingsUpdate(BaseModel):
    days: List[str]
    start_time: str
    end_time: str
    daily_cap: int
    delay_minutes: int
    sender_daily_cap: Optional[int] = None


class SenderSelect(BaseModel):
    sender_id: int


class RecipientsPaste(BaseModel):
    raw: str


class RecipientsGoogleSheet(BaseModel):
    url: str
    tab_name: str
    header_row: int
    use_private: Optional[bool] = False
    mapping: Dict[str, str]


class RecipientsSelectExisting(BaseModel):
    contact_ids: List[int]


class TestSendRequest(BaseModel):
    recipient_email: str
    preview_contact_id: Optional[int] = None


class SettingsUpdate(BaseModel):
    timezone: str
    max_daily_cap: int
    bounce_rate_pause_threshold: float
    max_consecutive_errors: int


class SaveCredentialsRequest(BaseModel):
    content: str


class SenderUpdate(BaseModel):
    display_name: str = ""
    daily_cap: int = 10
    group_name: str = ""


class TemplateCreate(BaseModel):
    title: str
    subject: str
    body: str


class GroupCreate(BaseModel):
    name: str
