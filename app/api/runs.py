# GET /runs, /runs/{id}

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Run

router = APIRouter(prefix="/runs", tags=["runs"])


def run_dict(r: Run, with_steps: bool = False) -> dict:
    d = {
        "id": str(r.id),
        "repo": r.repo_full_name,
        "pr_number": r.pr_number,
        "head_sha": r.head_sha,
        "status": r.status,
        "attempts": r.attempts,
        "error": r.error,
        "created_at": r.created_at,
        "started_at": r.started_at,
        "finished_at": r.finished_at,
    }
    if with_steps:
        d["steps"] = [
            {
                "name": s.name,
                "status": s.status,
                "started_at": s.started_at,
                "finished_at": s.finished_at,
                "error": s.error,
                "meta": s.meta,
            }
            for s in sorted(r.steps, key=lambda s: s.started_at or r.created_at)
        ]
    return d


@router.get("")
def list_runs(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.scalars(select(Run).order_by(Run.created_at.desc()).limit(min(limit, 100))).all()
    return [run_dict(r) for r in rows]


@router.get("/{run_id}")
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_dict(run, with_steps=True)