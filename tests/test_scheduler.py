import pytest
from unittest.mock import patch, MagicMock
from src.scheduler import attachment_path_for_send
from src.models import AppConfig

@patch("src.scheduler.db.resolve_project_path")
def test_attachment_path_for_send(mock_resolve):
    config = AppConfig()

    # Campaign with no attachment
    campaign_no_attachment = {"attachment_path": ""}
    assert attachment_path_for_send(config, campaign_no_attachment) is None

    # Campaign with attachment but path doesn't exist
    mock_path = MagicMock()
    mock_path.exists.return_value = False
    mock_resolve.return_value = mock_path
    
    campaign_with_attachment = {"attachment_path": "test.pdf"}
    assert attachment_path_for_send(config, campaign_with_attachment) is None
    
    # Campaign with attachment that exists
    mock_path.exists.return_value = True
    assert attachment_path_for_send(config, campaign_with_attachment) == "test.pdf"

