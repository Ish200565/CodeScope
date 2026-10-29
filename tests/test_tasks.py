from app.models import Run
from app.worker import tasks
from app.worker.exceptions import PermanentError
from tests.conftest import TestingSession
from tests.test_webhook import post, pr_payload


def make_run(client) -> str:
    post(client, pr_payload())
    with TestingSession() as db:
        return str(db.query(Run).one().id)


def get_run(run_id):
    with TestingSession() as db:
        r = db.query(Run).one()
        return r.status, r.attempts, r.error, len(r.steps)


def test_webhook_enqueues_job(client, monkeypatch):
    calls = []
    monkeypatch.setattr(tasks.process_run, "delay", lambda rid: calls.append(rid))
    post(client, pr_payload())
    assert len(calls) == 1


def test_process_run_succeeds(client, monkeypatch):
    monkeypatch.setattr(tasks, "SessionLocal", TestingSession)
    monkeypatch.setattr(tasks, "do_work", lambda run: None)
    run_id = make_run(client)
    tasks.process_run.apply(args=[run_id])
    status, attempts, error, steps = get_run(run_id)
    assert (status, attempts, error, steps) == ("succeeded", 1, None, 1)


def test_permanent_error_fails_fast(client, monkeypatch):
    def boom(run):
        raise PermanentError("bad data")

    monkeypatch.setattr(tasks, "SessionLocal", TestingSession)
    monkeypatch.setattr(tasks, "do_work", boom)
    run_id = make_run(client)
    tasks.process_run.apply(args=[run_id])
    status, attempts, error, _ = get_run(run_id)
    assert status == "failed" and attempts == 1 and "permanent" in error


def test_finished_run_is_skipped(client, monkeypatch):
    monkeypatch.setattr(tasks, "SessionLocal", TestingSession)
    monkeypatch.setattr(tasks, "do_work", lambda run: None)
    run_id = make_run(client)
    tasks.process_run.apply(args=[run_id])
    tasks.process_run.apply(args=[run_id])   # simulated redelivery
    assert get_run(run_id)[1] == 1           # still one attempt