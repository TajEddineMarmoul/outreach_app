import json
from pathlib import Path
from fastapi.testclient import TestClient

from api.main import app, get_db

client = TestClient(app)
AUTH_HEADERS = {"Authorization": "Bearer mock_test_user"}

def test_api_campaigns_flow():
    # 1. Get campaigns list
    res = client.get("/api/campaigns", headers=AUTH_HEADERS)
    assert res.status_code == 200
    initial_count = len(res.json())

    # 2. Create campaign
    res = client.post("/api/campaigns", json={"name": "Smoke Test Campaign"}, headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Smoke Test Campaign"
    campaign_id = data["id"]

    # 3. Get single campaign
    res = client.get(f"/api/campaigns/{campaign_id}", headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert res.json()["name"] == "Smoke Test Campaign"

    # 4. Patch campaign composer
    res = client.patch(
        f"/api/campaigns/{campaign_id}/composer",
        json={
            "subject_template": "Hello {{ First_Name }}",
            "body_template": "Welcome to {{ Company_Name }}.",
            "fallback_body_template": "Welcome fallback.",
            "attachment_path": ""
        },
        headers=AUTH_HEADERS
    )
    assert res.status_code == 200

    # 5. Check campaign updated templates
    res = client.get(f"/api/campaigns/{campaign_id}", headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert res.json()["subject_template"] == "Hello {{ First_Name }}"

    # 6. Delete campaign
    res = client.delete(f"/api/campaigns/{campaign_id}", headers=AUTH_HEADERS)
    assert res.status_code == 200

    # 7. Verify deleted
    res = client.get(f"/api/campaigns/{campaign_id}", headers=AUTH_HEADERS)
    assert res.status_code == 404

def test_api_senders():
    res = client.get("/api/senders", headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_api_settings():
    res = client.get("/api/settings", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert "timezone" in data
    assert "max_daily_cap" in data
