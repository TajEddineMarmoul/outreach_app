from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from api.main import app
from src.platform import db as platform_db
from src.platform.jobs import create_send_jobs_for_next_batch
from src.platform.models import Base, Campaign, CampaignRecipient, Contact, Sender, SenderGroup, SendJob
from src.platform.services import ensure_user
from src.platform.time import utcnow


USER_ID = "mock_app_user"
HEADERS = {"Authorization": f"Bearer {USER_ID}"}


def make_session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'app.db'}", future=True, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def install_session_override(session_factory):
    def override_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[platform_db.get_session] = override_session


def clear_session_override():
    app.dependency_overrides.pop(platform_db.get_session, None)


def test_sender_group_can_hold_multiple_senders_and_delete_clears_credentials(tmp_path):
    session_factory = make_session_factory(tmp_path)
    install_session_override(session_factory)
    try:
        client = TestClient(app)
        group_res = client.post("/api/sender-groups", json={"name": "Primary"}, headers=HEADERS)
        assert group_res.status_code == 200
        group_id = group_res.json()["id"]

        session = session_factory()
        ensure_user(session, USER_ID)
        session.add_all(
            [
                Sender(
                    user_id=USER_ID,
                    group_id=group_id,
                    email="one@example.com",
                    display_name="One",
                    status="connected",
                    daily_cap=10,
                    encrypted_oauth_credentials="encrypted-1",
                    scopes=["https://www.googleapis.com/auth/gmail.send"],
                    connected_at=utcnow(),
                ),
                Sender(
                    user_id=USER_ID,
                    group_id=group_id,
                    email="two@example.com",
                    display_name="Two",
                    status="connected",
                    daily_cap=10,
                    encrypted_oauth_credentials="encrypted-2",
                    scopes=["https://www.googleapis.com/auth/gmail.send"],
                    connected_at=utcnow(),
                ),
            ]
        )
        session.commit()
        session.close()

        groups = client.get("/api/sender-groups", headers=HEADERS).json()
        assert groups[0]["connected_sender_count"] == 2
        assert {sender["email"] for sender in groups[0]["senders"]} == {"one@example.com", "two@example.com"}

        sender_id = groups[0]["senders"][0]["id"]
        delete_res = client.delete(f"/api/senders/{sender_id}", headers=HEADERS)
        assert delete_res.status_code == 200

        session = session_factory()
        removed = session.get(Sender, sender_id)
        assert removed.status == "removed"
        assert removed.encrypted_oauth_credentials is None
        session.close()

        groups = client.get("/api/sender-groups", headers=HEADERS).json()
        assert len(groups[0]["senders"]) == 1

        second_sender_id = groups[0]["senders"][0]["id"]
        assert client.delete(f"/api/senders/{second_sender_id}", headers=HEADERS).status_code == 200
        delete_group = client.delete(f"/api/sender-groups/{group_id}", headers=HEADERS)
        assert delete_group.status_code == 200

        removed_connect_route = client.post("/api/senders/connect", headers=HEADERS)
        assert removed_connect_route.status_code == 405
    finally:
        clear_session_override()


def test_campaign_selects_sender_group_not_sender(tmp_path):
    session_factory = make_session_factory(tmp_path)
    install_session_override(session_factory)
    try:
        client = TestClient(app)
        group_id = client.post("/api/sender-groups", json={"name": "Outbound"}, headers=HEADERS).json()["id"]

        res = client.patch(
            "/api/campaigns/19/sender-group",
            json={"sender_group_id": group_id},
            headers=HEADERS,
        )
        assert res.status_code == 200
        assert res.json()["sender_group"]["id"] == group_id

        session = session_factory()
        campaign = session.get(Campaign, 19)
        assert campaign.selected_sender_group_id == group_id
        assert campaign.user_id == USER_ID
        session.close()
    finally:
        clear_session_override()


def test_next_batch_queues_one_email_per_connected_sender(tmp_path, monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    session_factory = make_session_factory(tmp_path)
    session = session_factory()
    ensure_user(session, USER_ID)
    group = SenderGroup(user_id=USER_ID, name="Three senders")
    session.add(group)
    session.flush()
    senders = [
        Sender(
            user_id=USER_ID,
            group_id=group.id,
            email=f"sender{i}@example.com",
            display_name=f"Sender {i}",
            status="connected",
            daily_cap=10,
            encrypted_oauth_credentials=f"encrypted-{i}",
            scopes=["https://www.googleapis.com/auth/gmail.send"],
            connected_at=utcnow(),
        )
        for i in range(3)
    ]
    campaign = Campaign(
        user_id=USER_ID,
        selected_sender_group_id=group.id,
        name="Batch test",
        subject_template="Hi {{ email }}",
        body_template="Body",
        fallback_body_template="Body",
        status="draft",
    )
    session.add_all([*senders, campaign])
    session.flush()
    contacts = [
        Contact(
            user_id=USER_ID,
            email_normalized=f"lead{i}@example.com",
            status="approved",
            custom_fields={"email": f"lead{i}@example.com", "f": f"value{i}"},
        )
        for i in range(5)
    ]
    session.add_all(contacts)
    session.flush()
    session.add_all(
        [
            CampaignRecipient(campaign_id=campaign.id, contact_id=contact.id, status="approved")
            for contact in contacts
        ]
    )
    session.commit()

    result = create_send_jobs_for_next_batch(session, user_id=USER_ID, campaign_id=campaign.id, delay_minutes=7)
    assert result["created"] == 3
    assert result["queued"] == 0

    jobs = list(session.scalars(select(SendJob).order_by(SendJob.id)))
    assert len(jobs) == 3
    assert len({job.sender_id for job in jobs}) == 3
    assert len({job.recipient_id for job in jobs}) == 3
    assert all(job.status == "queued" for job in jobs)
    session.close()
