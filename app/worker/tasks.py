import logging
import time
import uuid
from contextlib import contextmanager

from app.config import settings
from app.db import SessionLocal
from app.models import Run, StepRun, utcnow
from app.worker.celery_app import celery_app
from app.worker.exceptions import PermanentError, TransientError

logger = logging.getLogger(__name__)


@contextmanager
def step(db, run, name):
    """Record a unit of work in step_runs: running -> succeeded/failed."""
    s = StepRun(run_id=run.id, name=name, status="running", started_at=utcnow())
    db.add(s)
    db.commit()
    try:
        yield s
    except Exception as e:
        s.status = "failed"
        s.error = str(e)[:2000]
        s.finished_at = utcnow()
        db.commit()
        raise
    else:
        s.status = "succeeded"
        s.finished_at = utcnow()
        db.commit()


def do_work(run: Run) -> None:
    """Placeholder for the real pipeline (Days 4-7 and Week 2 replace this)."""
    mode = settings.fail_mode
    if mode == "transient":
        raise TransientError("simulated transient failure")
    if mode == "permanent":
        raise PermanentError("simulated permanent failure")
    if mode == "flaky" and run.attempts < 3:
        raise TransientError(f"simulated flaky failure on attempt {run.attempts}")
    time.sleep(5)


def mark_failed(db, run, message: str) -> None:
    run.status = "failed"
    run.error = message[:2000]
    run.finished_at = utcnow()
    db.commit()
    logger.error("run %s failed: %s", run.id, message)


@celery_app.task(
    bind=True,
    acks_late=True,
    autoretry_for=(TransientError,),
    retry_backoff=True,        # 1s, 2s, 4s ...
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def process_run(self, run_id: str):
    with SessionLocal() as db:
        run = db.get(Run, uuid.UUID(run_id))
        if run is None:
            logger.error("run %s not found", run_id)
            return  # nothing to retry: the row doesn't exist

        # Idempotency: a redelivered job for a finished run does nothing
        if run.status in ("succeeded", "failed"):
            logger.info("run %s already %s, skipping", run.id, run.status)
            return

        run.status = "running"
        run.attempts += 1
        run.started_at = run.started_at or utcnow()
        run.error = None
        db.commit()
        logger.info("run %s started (attempt %s)", run.id, run.attempts)

        try:
            with step(db, run, "placeholder_work"):
                do_work(run)
        except PermanentError as e:
            mark_failed(db, run, f"permanent: {e}")
            return
        except TransientError as e:
            if self.request.retries >= self.max_retries:
                mark_failed(db, run, f"gave up after {run.attempts} attempts: {e}")
                return
            run.error = f"retrying: {e}"
            db.commit()
            logger.warning("run %s transient error, will retry: %s", run.id, e)
            raise  # autoretry_for schedules the retry with backoff
        except Exception as e:  # unexpected bug: don't retry forever
            mark_failed(db, run, f"unexpected: {e!r}")
            return

        run.status = "succeeded"
        run.error = None
        run.finished_at = utcnow()
        db.commit()
        logger.info("run %s succeeded", run.id)