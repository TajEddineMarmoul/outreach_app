import base64
import email
from email.message import EmailMessage
from pathlib import Path
from src.gmail_sender import build_message

def test_build_message_plain_text():
    raw_msg = build_message(
        sender="test@example.com",
        recipient="user@example.com",
        subject="Test Subject",
        body="Hello world",
        attachment_path=None
    )
    
    assert "raw" in raw_msg
    
    # decode back
    msg_bytes = base64.urlsafe_b64decode(raw_msg["raw"].encode("ascii"))
    msg = email.message_from_bytes(msg_bytes)
    
    assert msg["To"] == "user@example.com"
    assert msg["From"] == "test@example.com"
    assert msg["Subject"] == "Test Subject"
    assert not msg.is_multipart()
    assert msg.get_content_type() == "text/plain"
    assert "Hello world" in msg.get_payload()

def test_build_message_html():
    raw_msg = build_message(
        sender="test@example.com",
        recipient="user@example.com",
        subject="Test HTML",
        body="<p>Hello <b>world</b></p>",
        attachment_path=None
    )
    
    msg_bytes = base64.urlsafe_b64decode(raw_msg["raw"].encode("ascii"))
    msg = email.message_from_bytes(msg_bytes)
    
    assert not msg.is_multipart()
    assert msg.get_content_type() == "text/html"
    assert "<p>Hello <b>world</b></p>" in msg.get_payload()

def test_build_message_with_attachment(tmp_path):
    # Create a dummy attachment
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy content")
    
    raw_msg = build_message(
        sender="test@example.com",
        recipient="user@example.com",
        subject="Attachment Test",
        body="Check the attachment",
        attachment_path=str(dummy_pdf)
    )
    
    msg_bytes = base64.urlsafe_b64decode(raw_msg["raw"].encode("ascii"))
    msg = email.message_from_bytes(msg_bytes)
    
    assert msg.is_multipart()
    
    parts = list(msg.walk())
    assert len(parts) >= 3 # multipart, text, application/pdf
    
    pdf_part = None
    for part in parts:
        if part.get_content_type() == "application/pdf":
            pdf_part = part
            
    assert pdf_part is not None
    assert pdf_part.get_filename() == "test.pdf"

