import uuid

from app.db import SessionLocal
from app.models import Run
from app.worker.tasks import process_run

with SessionLocal() as db:
    run = Run(
        delivery_id=str(uuid.uuid4()),
        repo_full_name="Ish200565/test_repo",
        pr_number=1,
        head_sha=uuid.uuid4().hex + "0" * 8,
        status="queued",
    )
    db.add(run)
    db.commit()
    process_run.delay(str(run.id))
    print("created run", run.id)