import hashlib
import hmac
import json

from app.models import Run
from tests.conftest import TestingSession

SECRET = "testsecret"


def sign(body: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


def pr_payload(action="opened", sha="a" * 40, number=1):
    return {
        "action": action,
        "pull_request": {"number": number, "head": {"sha": sha}},
        "repository": {"full_name": "ishika/test-repo"},
        "installation": {"id": 123},
    }


def post(client, payload, event="pull_request", delivery="d-1", signature=None):
    body = json.dumps(payload).encode()
    headers = {
        "X-GitHub-Event": event,
        "X-GitHub-Delivery": delivery,
        "X-Hub-Signature-256": signature if signature is not None else sign(body),
        "Content-Type": "application/json",
    }
    return client.post("/webhook/github", content=body, headers=headers)


def run_count() -> int:
    with TestingSession() as db:
        return db.query(Run).count()


def test_valid_webhook_creates_run(client):
    r = post(client, pr_payload())
    assert r.status_code == 202
    assert r.json()["status"] == "queued"
    assert run_count() == 1


def test_bad_signature_rejected(client):
    r = post(client, pr_payload(), signature="sha256=deadbeef")
    assert r.status_code == 401
    assert run_count() == 0


def test_missing_signature_rejected(client):
    body = json.dumps(pr_payload()).encode()
    r = client.post(
        "/webhook/github",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-GitHub-Delivery": "d-1"},
    )
    assert r.status_code == 401


def test_same_delivery_id_is_idempotent(client):
    post(client, pr_payload(sha="b" * 40), delivery="same")
    r = post(client, pr_payload(sha="c" * 40), delivery="same")
    assert r.json()["status"] == "duplicate"
    assert run_count() == 1


def test_same_commit_different_delivery_is_deduped(client):
    post(client, pr_payload(), delivery="d-1")
    r = post(client, pr_payload(), delivery="d-2")
    assert r.json()["status"] == "duplicate"
    assert run_count() == 1


def test_new_commit_creates_new_run(client):
    post(client, pr_payload(sha="a" * 40), delivery="d-1")
    post(client, pr_payload(action="synchronize", sha="b" * 40), delivery="d-2")
    assert run_count() == 2


def test_non_pr_event_ignored(client):
    r = post(client, {"zen": "hi"}, event="push")
    assert r.status_code == 200 and r.json()["status"] == "ignored"
    assert run_count() == 0


def test_irrelevant_action_ignored(client):
    r = post(client, pr_payload(action="closed"))
    assert r.json()["status"] == "ignored"
    assert run_count() == 0


def test_ping_returns_pong(client):
    assert post(client, {"zen": "hi"}, event="ping").json()["status"] == "pong"