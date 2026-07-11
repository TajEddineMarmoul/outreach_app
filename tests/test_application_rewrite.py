from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from api.main import app
from api.routers import campaign_delivery, oauth as oauth_router
from src.platform import db as platform_db
from src.platform import jobs as platform_jobs
from src.platform import oauth as platform_oauth
from src.platform import scheduler as platform_scheduler
from src.platform import services as platform_services
from src.platform import worker as platform_worker
from src.platform.jobs import create_send_jobs_for_next_batch
from src.platform.models import Base, Campaign, CampaignRecipient, Contact, OAuthState, Sender, SenderGroup, SendJob, SendLog
from src.platform.security import decrypt_text
from src.platform.services import ensure_user
from src.platform.time import utcnow
from src.db.contact_repo import insert_contact


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


def test_contact_insert_uses_pending_status_without_implicit_imports():
    connection = MagicMock()
    assert insert_contact(connection, {"email": "lead@example.com"}, USER_ID) is True
    inserted_data = connection.execute.call_args.args[1]
    assert inserted_data["status"] == "pending"
    assert inserted_data["user_id"] == USER_ID
    assert inserted_data["email_normalized"] == "lead@example.com"


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


def test_group_oauth_connect_delete_and_reconnect_stays_in_database(tmp_path, monkeypatch):
    session_factory = make_session_factory(tmp_path)
    install_session_override(session_factory)
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(
        json.dumps(
            {
                "web": {
                    "client_id": "test-client",
                    "client_secret": "test-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
        ),
        encoding="utf-8",
    )

    start_flow = MagicMock()
    start_flow.code_verifier = "pkce-verifier"
    start_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth", "ignored")
    monkeypatch.setattr(platform_oauth, "credentials_file_path", lambda: credentials_path)
    monkeypatch.setattr(
        platform_oauth.Flow,
        "from_client_secrets_file",
        lambda *_args, **_kwargs: start_flow,
    )

    exchanged_credentials = MagicMock()
    exchanged_credentials.scopes = ["https://www.googleapis.com/auth/gmail.send"]
    exchanged_credentials.to_json.return_value = json.dumps(
        {"token": "access-token", "refresh_token": "refresh-token"}
    )
    exchange_flow = MagicMock()
    exchange_flow.credentials = exchanged_credentials
    monkeypatch.setattr(oauth_router, "flow_from_state", lambda _state: exchange_flow)
    monkeypatch.setattr(
        oauth_router,
        "oauth_email_for_credentials",
        lambda _credentials: "sender@example.com",
    )

    try:
        client = TestClient(app)
        group_id = client.post(
            "/api/sender-groups",
            json={"name": "OAuth group"},
            headers=HEADERS,
        ).json()["id"]

        def connect_sender() -> int:
            start_response = client.post(
                f"/api/sender-groups/{group_id}/senders/oauth/start",
                headers=HEADERS,
            )
            assert start_response.status_code == 200
            assert start_response.json()["auth_url"].startswith("https://accounts.google.com/")

            session = session_factory()
            oauth_state = session.scalar(
                select(OAuthState)
                .where(OAuthState.group_id == group_id, OAuthState.used_at.is_(None))
                .order_by(OAuthState.created_at.desc())
            )
            assert oauth_state.user_id == USER_ID
            assert oauth_state.code_verifier == "pkce-verifier"
            state_value = oauth_state.state
            session.close()

            callback_response = client.get(
                f"/api/oauth/callback?code=fake-code&state={state_value}",
                follow_redirects=False,
            )
            assert callback_response.status_code in (302, 307)
            assert "oauth=success" in callback_response.headers["location"]
            exchange_flow.fetch_token.assert_called_with(code="fake-code")

            session = session_factory()
            sender = session.scalar(
                select(Sender).where(Sender.user_id == USER_ID, Sender.email == "sender@example.com")
            )
            state = session.get(OAuthState, state_value)
            assert sender.group_id == group_id
            assert sender.status == "connected"
            assert json.loads(decrypt_text(sender.encrypted_oauth_credentials))["refresh_token"] == "refresh-token"
            assert state.used_at is not None
            sender_id = sender.id
            session.close()
            return sender_id

        sender_id = connect_sender()
        assert client.delete(f"/api/senders/{sender_id}", headers=HEADERS).status_code == 200
        reconnected_sender_id = connect_sender()
        assert reconnected_sender_id == sender_id

        session = session_factory()
        reconnected = session.get(Sender, sender_id)
        assert reconnected.status == "connected"
        assert reconnected.removed_at is None
        session.close()

        assert list(tmp_path.rglob("*.json")) == [credentials_path]
        assert client.post("/api/oauth/start", headers=HEADERS).status_code == 404
        assert client.post("/api/oauth/callback", json={}, headers=HEADERS).status_code == 405
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
            CampaignRecipient(campaign_id=campaign.id, contact_id=contact.id)
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
    assert [(job.sender_id, job.recipient_id) for job in jobs] == [
        (senders[index].id, contacts[index].id) for index in range(3)
    ]

    for job in jobs:
        job.status = "sent"
        session.get(
            CampaignRecipient,
            {"campaign_id": campaign.id, "contact_id": job.recipient_id},
        ).status = "sent"
    session.commit()

    second_batch = create_send_jobs_for_next_batch(
        session,
        user_id=USER_ID,
        campaign_id=campaign.id,
        delay_minutes=7,
    )
    assert second_batch["created"] == 2
    assert len(list(session.scalars(select(SendJob)))) == 5
    session.close()


def test_next_batch_skips_capped_senders_and_uses_remaining_sender(tmp_path):
    session_factory = make_session_factory(tmp_path)
    session = session_factory()
    ensure_user(session, USER_ID)
    group = SenderGroup(user_id=USER_ID, name="Cap handling")
    session.add(group)
    session.flush()
    capped = Sender(
        user_id=USER_ID,
        group_id=group.id,
        email="capped@example.com",
        status="connected",
        daily_cap=1,
        encrypted_oauth_credentials="encrypted-1",
    )
    available = Sender(
        user_id=USER_ID,
        group_id=group.id,
        email="available@example.com",
        status="connected",
        daily_cap=10,
        encrypted_oauth_credentials="encrypted-2",
    )
    campaign = Campaign(
        user_id=USER_ID,
        selected_sender_group_id=group.id,
        name="Cap test",
        subject_template="Hello",
        body_template="Body",
        fallback_body_template="Body",
        status="sending",
    )
    contact = Contact(user_id=USER_ID, email_normalized="lead@example.com", status="approved")
    session.add_all([capped, available, campaign, contact])
    session.flush()
    session.add(CampaignRecipient(campaign_id=campaign.id, contact_id=contact.id))
    session.add(
        SendLog(
            user_id=USER_ID,
            campaign_id=campaign.id,
            sender_id=capped.id,
            recipient_email="previous@example.com",
            sender_email=capped.email,
            status="sent",
            sent_at=utcnow(),
        )
    )
    session.commit()

    result = create_send_jobs_for_next_batch(session, user_id=USER_ID, campaign_id=campaign.id)
    job = session.get(SendJob, result["job_ids"][0])
    assert result["created"] == 1
    assert job.sender_id == available.id
    session.close()


def test_scheduler_pauses_send_now_but_keeps_autopilot_when_all_senders_are_capped(tmp_path, monkeypatch):
    session_factory = make_session_factory(tmp_path)
    session = session_factory()
    ensure_user(session, USER_ID)
    now = utcnow()
    campaigns = [
        Campaign(
            user_id=USER_ID,
            name="Send now capped",
            subject_template="Hello",
            body_template="Body",
            fallback_body_template="Body",
            status="sending",
            scheduled_at=now - timedelta(seconds=1),
            send_settings={"mode": "send_now"},
        ),
        Campaign(
            user_id=USER_ID,
            name="Autopilot capped",
            subject_template="Hello",
            body_template="Body",
            fallback_body_template="Body",
            status="autopilot",
            scheduled_at=now - timedelta(seconds=1),
            send_settings={"mode": "autopilot", "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]},
        ),
    ]
    session.add_all(campaigns)
    session.commit()
    monkeypatch.setattr(
        platform_scheduler,
        "create_send_jobs_for_next_batch",
        lambda *_args, **_kwargs: {
            "created": 0,
            "job_ids": [],
            "reason_code": "daily_caps_reached",
            "reason": "All senders reached their daily cap",
        },
    )
    platform_scheduler.enqueue_due_campaign_batches(session)

    assert campaigns[0].status == "paused"
    assert campaigns[0].scheduled_at is None
    assert campaigns[1].status == "autopilot"
    assert campaigns[1].scheduled_at > now
    session.close()


def test_campaign_delivery_control_routes_are_registered_once():
    registered_routes = []
    for route in app.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            registered_routes.extend(original_router.routes)
        else:
            registered_routes.append(route)

    for action in ("send-now", "schedule", "autopilot/start", "pause", "resume", "stop"):
        path = f"/api/campaigns/{{campaign_id}}/{action}"
        matches = [
            route
            for route in registered_routes
            if getattr(route, "path", None) == path
            and "POST" in (getattr(route, "methods", set()) or set())
        ]
        assert len(matches) == 1, f"{path} is registered {len(matches)} times"


def test_worker_tick_requires_token_and_runs_without_browser(tmp_path, monkeypatch):
    session_factory = make_session_factory(tmp_path)
    monkeypatch.setattr(campaign_delivery, "recover_stale_jobs", lambda **_kwargs: 2)
    monkeypatch.setattr(campaign_delivery, "run_worker_cycle", lambda **_kwargs: 3)
    monkeypatch.setenv("WORKER_TICK_TOKEN", "test-worker-token")

    client = TestClient(app)
    assert client.post("/internal/worker/tick").status_code == 401
    response = client.post(
        "/internal/worker/tick",
        headers={"X-Worker-Token": "test-worker-token"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "recovered": 2, "processed": 3}


def test_send_now_creates_jobs_without_sending_inside_api_process(tmp_path):
    session_factory = make_session_factory(tmp_path)
    install_session_override(session_factory)
    try:
        session = session_factory()
        ensure_user(session, USER_ID)
        group = SenderGroup(user_id=USER_ID, name="Send now")
        session.add(group)
        session.flush()
        sender = Sender(
            user_id=USER_ID,
            group_id=group.id,
            email="sender@example.com",
            display_name="Sender",
            status="connected",
            daily_cap=10,
            encrypted_oauth_credentials="encrypted",
            scopes=["https://www.googleapis.com/auth/gmail.send"],
            connected_at=utcnow(),
        )
        campaign = Campaign(
            user_id=USER_ID,
            selected_sender_group_id=group.id,
            name="Send now test",
            subject_template="Hello",
            body_template="Body",
            fallback_body_template="Fallback",
            status="draft",
        )
        contact = Contact(
            user_id=USER_ID,
            email_normalized="lead@example.com",
            status="approved",
            custom_fields={},
        )
        session.add_all([sender, campaign, contact])
        session.flush()
        session.add(CampaignRecipient(campaign_id=campaign.id, contact_id=contact.id))
        session.commit()
        campaign_id = campaign.id
        session.close()

        response = TestClient(app).post(
            f"/api/campaigns/{campaign_id}/send-now",
            json={"delay_minutes": 2},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["queued"] == 1

        session = session_factory()
        persisted_campaign = session.get(Campaign, campaign_id)
        job = session.scalar(select(SendJob).where(SendJob.campaign_id == campaign_id))
        recipient = session.get(
            CampaignRecipient,
            {"campaign_id": campaign_id, "contact_id": contact.id},
        )
        assert persisted_campaign.status == "sending"
        assert persisted_campaign.send_settings["delay_minutes"] == 2
        assert job.status == "queued"
        assert recipient.status == "queued"
        session.close()
    finally:
        clear_session_override()


def test_send_now_does_not_succeed_silently_when_nothing_is_queued(tmp_path):
    session_factory = make_session_factory(tmp_path)
    install_session_override(session_factory)
    try:
        session = session_factory()
        ensure_user(session, USER_ID)
        group = SenderGroup(user_id=USER_ID, name="Empty campaign")
        session.add(group)
        session.flush()
        session.add(
            Sender(
                user_id=USER_ID,
                group_id=group.id,
                email="sender@example.com",
                display_name="Sender",
                status="connected",
                daily_cap=10,
                encrypted_oauth_credentials="encrypted",
                scopes=["https://www.googleapis.com/auth/gmail.send"],
                connected_at=utcnow(),
            )
        )
        campaign = Campaign(
            user_id=USER_ID,
            selected_sender_group_id=group.id,
            name="Empty",
            subject_template="Hello",
            body_template="Body",
            fallback_body_template="Fallback",
            status="draft",
        )
        session.add(campaign)
        session.commit()
        campaign_id = campaign.id
        session.close()

        response = TestClient(app).post(
            f"/api/campaigns/{campaign_id}/send-now",
            json={"delay_minutes": 2},
            headers=HEADERS,
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "No unsent approved recipients are ready"

        schedule_response = TestClient(app).post(
            f"/api/campaigns/{campaign_id}/schedule",
            json={"delay_minutes": 2, "scheduled_at": utcnow().isoformat()},
            headers=HEADERS,
        )
        assert schedule_response.status_code == 409
        assert schedule_response.json()["detail"] == "Campaign has no approved recipients"
    finally:
        clear_session_override()


def test_perform_send_job_sends_and_persists_delivery_state(tmp_path, monkeypatch):
    session_factory = make_session_factory(tmp_path)
    session = session_factory()
    ensure_user(session, USER_ID)
    group = SenderGroup(user_id=USER_ID, name="Delivery")
    session.add(group)
    session.flush()
    sender = Sender(
        user_id=USER_ID,
        group_id=group.id,
        email="sender@example.com",
        display_name="Sender",
        status="connected",
        daily_cap=10,
        encrypted_oauth_credentials="encrypted",
        scopes=["https://www.googleapis.com/auth/gmail.send"],
        connected_at=utcnow(),
    )
    campaign = Campaign(
        user_id=USER_ID,
        selected_sender_group_id=group.id,
        name="Delivery test",
        subject_template="Hello {{ first_name }}",
        body_template="Message for {{ email }}",
        fallback_body_template="Fallback",
        status="sending",
    )
    contact = Contact(
        user_id=USER_ID,
        email_normalized="lead@example.com",
        status="approved",
        custom_fields={"first_name": "Ada"},
    )
    session.add_all([sender, campaign, contact])
    session.flush()
    recipient = CampaignRecipient(campaign_id=campaign.id, contact_id=contact.id, status="queued")
    job = SendJob(
        user_id=USER_ID,
        campaign_id=campaign.id,
        recipient_id=contact.id,
        sender_id=sender.id,
        status="queued",
        scheduled_for=utcnow(),
        batch_id="batch",
        idempotency_key=f"campaign:{campaign.id}:recipient:{contact.id}",
    )
    session.add_all([recipient, job])
    session.commit()
    job_id = job.id
    session.close()

    monkeypatch.setattr(platform_jobs, "SessionLocal", session_factory)
    monkeypatch.setattr(platform_jobs, "gmail_service_for_sender", lambda _session, _sender: object())
    monkeypatch.setattr(
        platform_jobs,
        "send_email",
        lambda **_kwargs: SimpleNamespace(message_id="gmail-message", thread_id="gmail-thread"),
    )

    assert platform_jobs.perform_send_job(job_id)["status"] == "sent"

    session = session_factory()
    persisted_job = session.get(SendJob, job_id)
    persisted_recipient = session.get(
        CampaignRecipient,
        {"campaign_id": campaign.id, "contact_id": contact.id},
    )
    log = session.scalar(select(SendLog).where(SendLog.campaign_id == campaign.id))
    assert persisted_job.status == "sent"
    assert persisted_job.attempts == 1
    assert persisted_recipient.status == "sent"
    assert log.status == "sent"
    assert log.contact_id == contact.id
    assert log.gmail_message_id == "gmail-message"
    session.close()


def _seed_delivery_campaign(session_factory, *, recipient_count=4):
    session = session_factory()
    ensure_user(session, USER_ID)
    group = SenderGroup(user_id=USER_ID, name="Integration senders")
    session.add(group)
    session.flush()
    senders = [
        Sender(
            user_id=USER_ID,
            group_id=group.id,
            email=f"sender{index + 1}@example.com",
            display_name=f"Sender {index + 1}",
            status="connected",
            daily_cap=20,
            encrypted_oauth_credentials=f"encrypted-{index + 1}",
            scopes=["https://www.googleapis.com/auth/gmail.send"],
            connected_at=utcnow(),
        )
        for index in range(2)
    ]
    campaign = Campaign(
        user_id=USER_ID,
        selected_sender_group_id=group.id,
        name="HTTP delivery integration",
        subject_template="Hello {{ first_name }}",
        body_template="Message for {{ email }}",
        fallback_body_template="Fallback",
        status="draft",
    )
    session.add_all([*senders, campaign])
    session.flush()
    contacts = [
        Contact(
            user_id=USER_ID,
            email_normalized=f"lead{index + 1}@example.com",
            status="approved",
            custom_fields={"first_name": f"Lead {index + 1}"},
        )
        for index in range(recipient_count)
    ]
    session.add_all(contacts)
    session.flush()
    session.add_all(
        CampaignRecipient(campaign_id=campaign.id, contact_id=contact.id, status="approved")
        for contact in contacts
    )
    session.commit()
    result = campaign.id, [sender.id for sender in senders], [contact.id for contact in contacts]
    session.close()
    return result


def _install_fake_delivery(monkeypatch, session_factory, sent_requests):
    monkeypatch.setattr(platform_jobs, "SessionLocal", session_factory)
    monkeypatch.setattr(platform_worker, "SessionLocal", session_factory)
    monkeypatch.setattr(platform_jobs, "gmail_service_for_sender", lambda _session, _sender: object())

    def fake_send_email(**kwargs):
        sent_requests.append(kwargs)
        sequence = len(sent_requests)
        return SimpleNamespace(message_id=f"gmail-message-{sequence}", thread_id=f"gmail-thread-{sequence}")

    monkeypatch.setattr(platform_jobs, "send_email", fake_send_email)

def test_send_now_http_runs_two_sender_batches_through_fake_gmail(tmp_path, monkeypatch):
    session_factory = make_session_factory(tmp_path)
    install_session_override(session_factory)
    sent_requests = []
    _install_fake_delivery(monkeypatch, session_factory, sent_requests)
    try:
        campaign_id, sender_ids, contact_ids = _seed_delivery_campaign(session_factory)
        response = TestClient(app).post(
            f"/api/campaigns/{campaign_id}/send-now",
            json={"delay_minutes": 3},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["queued"] == 2
        assert sent_requests == []
        assert platform_worker.run_worker_cycle() == 2
        assert [request["sender"] for request in sent_requests] == [
            "sender1@example.com",
            "sender2@example.com",
        ]

        progress = TestClient(app).get(
            f"/api/campaigns/{campaign_id}/send-progress",
            headers=HEADERS,
        )
        assert progress.status_code == 200
        progress_data = progress.json()
        assert progress_data["campaign_status"] == "sending"
        assert progress_data["is_active"] is True
        assert progress_data["is_waiting"] is True
        assert progress_data["is_sending"] is False
        assert progress_data["sent_count"] == 2
        assert progress_data["next_batch_at"] is not None
        assert progress_data["delay_minutes"] == 3
        assert [sender["campaign_sent"] for sender in progress_data["senders"]] == [1, 1]
        assert all(sender["remaining_today"] == 19 for sender in progress_data["senders"])

        session = session_factory()
        campaign = session.get(Campaign, campaign_id)
        campaign.scheduled_at = utcnow() - timedelta(seconds=1)
        session.commit()
        session.close()
        assert platform_worker.run_worker_cycle() == 2

        session = session_factory()

        jobs = list(session.scalars(select(SendJob).order_by(SendJob.id)))
        logs = list(session.scalars(select(SendLog).order_by(SendLog.id)))
        assert [(job.sender_id, job.recipient_id) for job in jobs] == [
            (sender_ids[0], contact_ids[0]),
            (sender_ids[1], contact_ids[1]),
            (sender_ids[0], contact_ids[2]),
            (sender_ids[1], contact_ids[3]),
        ]
        assert len(logs) == 4
        assert all(log.status == "sent" and log.gmail_message_id for log in logs)
        assert len(sent_requests) == 4
        session.close()
    finally:
        clear_session_override()


def test_schedule_http_waits_for_scheduler_then_sends_through_fake_gmail(tmp_path, monkeypatch):
    session_factory = make_session_factory(tmp_path)
    install_session_override(session_factory)
    sent_requests = []
    _install_fake_delivery(monkeypatch, session_factory, sent_requests)
    try:
        campaign_id, _, _ = _seed_delivery_campaign(session_factory, recipient_count=2)
        due = utcnow() - timedelta(seconds=1)
        response = TestClient(app).post(
            f"/api/campaigns/{campaign_id}/schedule",
            json={"delay_minutes": 4, "scheduled_at": due.isoformat()},
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "scheduled"
        assert sent_requests == []

        session = session_factory()
        session.close()
        assert platform_worker.run_worker_cycle() == 2

        session = session_factory()
        assert len(sent_requests) == 2
        assert session.scalar(select(Campaign).where(Campaign.id == campaign_id)).send_settings["delay_minutes"] == 4
        assert session.scalar(select(SendLog).where(SendLog.campaign_id == campaign_id).limit(1)).status == "sent"
        session.close()
    finally:
        clear_session_override()


def test_autopilot_http_starts_and_sends_due_batch_through_fake_gmail(tmp_path, monkeypatch):
    session_factory = make_session_factory(tmp_path)
    install_session_override(session_factory)
    sent_requests = []
    _install_fake_delivery(monkeypatch, session_factory, sent_requests)
    try:
        campaign_id, _, _ = _seed_delivery_campaign(session_factory, recipient_count=2)
        due = utcnow() - timedelta(seconds=1)
        response = TestClient(app).post(
            f"/api/campaigns/{campaign_id}/autopilot/start",
            json={
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                "start_time": "00:00",
                "end_time": "23:59",
                "delay_minutes": 6,
                "scheduled_at": due.isoformat(),
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "autopilot"
        assert sent_requests == []

        session = session_factory()
        session.close()
        assert platform_worker.run_worker_cycle() == 2

        session = session_factory()
        campaign = session.get(Campaign, campaign_id)
        assert len(sent_requests) == 2
        assert campaign.status == "autopilot"
        assert campaign.send_settings["mode"] == "autopilot"
        assert campaign.send_settings["delay_minutes"] == 6
        assert len(list(session.scalars(select(SendLog).where(SendLog.campaign_id == campaign_id)))) == 2
        session.close()
    finally:
        clear_session_override()


def test_autopilot_waits_full_three_minutes_between_fake_gmail_batches(tmp_path, monkeypatch):
    session_factory = make_session_factory(tmp_path)
    install_session_override(session_factory)
    sent_requests = []
    _install_fake_delivery(monkeypatch, session_factory, sent_requests)
    try:
        campaign_id, sender_ids, contact_ids = _seed_delivery_campaign(session_factory, recipient_count=4)
        response = TestClient(app).post(
            f"/api/campaigns/{campaign_id}/autopilot/start",
            json={
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                "start_time": "00:00",
                "end_time": "23:59",
                "delay_minutes": 3,
                "scheduled_at": (utcnow() - timedelta(seconds=1)).isoformat(),
            },
            headers=HEADERS,
        )
        assert response.status_code == 200

        session = session_factory()
        session.close()
        assert platform_worker.run_worker_cycle() == 2

        session = session_factory()
        assert len(sent_requests) == 2
        next_batch_at = session.get(Campaign, campaign_id).scheduled_at

        monkeypatch.setattr(
            platform_scheduler,
            "utcnow",
            lambda: next_batch_at - timedelta(seconds=1),
        )
        monkeypatch.setattr(
            platform_worker,
            "utcnow",
            lambda: next_batch_at - timedelta(seconds=1),
        )
        session.close()
        assert platform_worker.run_worker_cycle() == 0
        assert len(sent_requests) == 2

        monkeypatch.setattr(
            platform_scheduler,
            "utcnow",
            lambda: next_batch_at + timedelta(seconds=1),
        )
        monkeypatch.setattr(
            platform_worker,
            "utcnow",
            lambda: next_batch_at + timedelta(seconds=1),
        )
        assert platform_worker.run_worker_cycle() == 2
        assert len(sent_requests) == 4

        session = session_factory()
        jobs = list(session.scalars(select(SendJob).order_by(SendJob.id)))
        assert [(job.sender_id, job.recipient_id) for job in jobs] == [
            (sender_ids[0], contact_ids[0]),
            (sender_ids[1], contact_ids[1]),
            (sender_ids[0], contact_ids[2]),
            (sender_ids[1], contact_ids[3]),
        ]
        assert len(list(session.scalars(select(SendLog).where(SendLog.campaign_id == campaign_id)))) == 4
        session.close()
    finally:
        clear_session_override()


def test_worker_recovers_interrupted_running_job(tmp_path, monkeypatch):
    session_factory = make_session_factory(tmp_path)
    monkeypatch.setattr(platform_worker, "SessionLocal", session_factory)
    campaign_id, sender_ids, contact_ids = _seed_delivery_campaign(session_factory, recipient_count=1)
    session = session_factory()
    recipient = session.get(
        CampaignRecipient,
        {"campaign_id": campaign_id, "contact_id": contact_ids[0]},
    )
    recipient.status = "queued"
    job = SendJob(
        user_id=USER_ID,
        campaign_id=campaign_id,
        recipient_id=contact_ids[0],
        sender_id=sender_ids[0],
        status="running",
        scheduled_for=utcnow() - timedelta(minutes=20),
        locked_at=utcnow() - timedelta(minutes=20),
        batch_id="interrupted-batch",
        idempotency_key=f"campaign:{campaign_id}:recipient:{contact_ids[0]}",
    )
    session.add(job)
    session.commit()
    job_id = job.id
    session.close()

    assert platform_worker.recover_stale_jobs(stale_after_minutes=10) == 1

    session = session_factory()
    recovered = session.get(SendJob, job_id)
    assert recovered.status == "retry"
    assert recovered.locked_at is None
    assert recovered.error_message == "Recovered after worker interruption"
    session.close()


def test_autopilot_compressed_day_resumes_after_five_minutes(tmp_path, monkeypatch):
    session_factory = make_session_factory(tmp_path)
    install_session_override(session_factory)
    sent_requests = []
    _install_fake_delivery(monkeypatch, session_factory, sent_requests)
    try:
        campaign_id, sender_ids, _ = _seed_delivery_campaign(session_factory, recipient_count=2)
        session = session_factory()
        senders = list(session.scalars(select(Sender).where(Sender.id.in_(sender_ids)).order_by(Sender.id)))
        senders[0].daily_cap = 1
        senders[1].status = "removed"
        senders[1].encrypted_oauth_credentials = None
        session.commit()
        session.close()

        start = utcnow()
        response = TestClient(app).post(
            f"/api/campaigns/{campaign_id}/autopilot/start",
            json={
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                "start_time": "00:00",
                "end_time": "23:59",
                "delay_minutes": 0,
                "scheduled_at": (start - timedelta(seconds=1)).isoformat(),
            },
            headers=HEADERS,
        )
        assert response.status_code == 200
        assert platform_worker.run_worker_cycle() == 1
        assert len(sent_requests) == 1

        compressed_next_day = start + timedelta(minutes=5)
        monkeypatch.setattr(
            platform_scheduler,
            "next_autopilot_run",
            lambda _session, _campaign, **_kwargs: compressed_next_day,
        )
        session = session_factory()
        campaign = session.get(Campaign, campaign_id)
        campaign.scheduled_at = start - timedelta(seconds=1)
        session.commit()
        session.close()
        assert platform_worker.run_worker_cycle() == 0

        session = session_factory()
        campaign = session.get(Campaign, campaign_id)
        assert campaign.status == "autopilot"
        assert campaign.scheduled_at.replace(tzinfo=compressed_next_day.tzinfo).timestamp() == compressed_next_day.timestamp()
        session.close()

        before_next_day = compressed_next_day - timedelta(seconds=1)
        monkeypatch.setattr(platform_scheduler, "utcnow", lambda: before_next_day)
        monkeypatch.setattr(platform_worker, "utcnow", lambda: before_next_day)
        assert platform_worker.run_worker_cycle() == 0
        assert len(sent_requests) == 1

        after_next_day = compressed_next_day + timedelta(seconds=1)
        monkeypatch.setattr(platform_scheduler, "utcnow", lambda: after_next_day)
        monkeypatch.setattr(platform_worker, "utcnow", lambda: after_next_day)
        monkeypatch.setattr(platform_services, "utcnow", lambda: start + timedelta(days=1, seconds=1))
        assert platform_worker.run_worker_cycle() == 1
        assert len(sent_requests) == 2

        session = session_factory()
        assert session.get(Campaign, campaign_id).status == "autopilot"
        assert len(list(session.scalars(select(SendLog).where(SendLog.campaign_id == campaign_id)))) == 2
        session.close()
    finally:
        clear_session_override()


def test_database_url_uses_postgres_in_development(monkeypatch):
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/outreach")
    monkeypatch.setenv("APP_ENV", "development")
    assert platform_db.get_database_url() == "postgresql+psycopg2://user:pass@localhost/outreach"
