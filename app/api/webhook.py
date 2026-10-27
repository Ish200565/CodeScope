import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Run
from app.security import verify_signature

router = APIRouter()
logger = logging.getLogger("uvicorn.error")  # shows up in `docker compose logs api`

HANDLED_ACTIONS = {"opened", "synchronize", "reopened"}


@router.post("/webhook/github")
async def github_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    x_github_delivery: str | None = Header(None),
):
    # 1. Raw bytes first: re-serialized JSON would not match the signature
    body = await request.body()

    # 2. Authenticate (fail closed if the secret is missing)
    if not settings.github_webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")
    if not verify_signature(settings.github_webhook_secret, body, x_hub_signature_256):
        logger.warning("webhook rejected: bad signature delivery=%s", x_github_delivery)
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 3. Filter events
    if x_github_event == "ping":
        logger.info("webhook ping delivery=%s", x_github_delivery)
        return {"status": "pong"}
    if x_github_event != "pull_request":
        logger.info("webhook ignored: event=%s delivery=%s", x_github_event, x_github_delivery)
        return {"status": "ignored", "reason": f"event {x_github_event}"}
    if not x_github_delivery:
        raise HTTPException(status_code=400, detail="Missing delivery id")

    try:
        payload = json.loads(body)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    action = payload.get("action")
    logger.info("webhook event=%s action=%s delivery=%s", x_github_event, action, x_github_delivery)

    if action not in HANDLED_ACTIONS:
        logger.info("webhook ignored: action=%s delivery=%s", action, x_github_delivery)
        return {"status": "ignored", "reason": f"action {action}"}

    try:
        pr = payload["pull_request"]
        repo = payload["repository"]["full_name"]
        number = pr["number"]
        sha = pr["head"]["sha"]
    except (KeyError, TypeError):
        raise HTTPException(status_code=400, detail="Malformed payload")

    # 4. Idempotency, layer 1: already have a live run for this exact commit?
    existing = db.scalar(
        select(Run).where(
            Run.repo_full_name == repo,
            Run.pr_number == number,
            Run.head_sha == sha,
            Run.status != "failed",
        )
    )
    if existing:
        logger.info("webhook duplicate (same commit): run=%s", existing.id)
        return {"status": "duplicate", "run_id": str(existing.id)}

    # 5. Create the run. Layer 2: unique delivery_id catches GitHub retries
    run = Run(
        delivery_id=x_github_delivery,
        repo_full_name=repo,
        pr_number=number,
        head_sha=sha,
        installation_id=(payload.get("installation") or {}).get("id"),
        status="queued",
    )
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info("webhook duplicate (same delivery id): %s", x_github_delivery)
        return {"status": "duplicate"}

    logger.info("run queued: run=%s repo=%s pr=%s sha=%s", run.id, repo, number, sha[:7])

    # Day 3: enqueue process_run.delay(str(run.id)) here, AFTER the commit

    return JSONResponse(status_code=202, content={"status": "queued", "run_id": str(run.id)})