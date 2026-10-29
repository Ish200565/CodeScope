import redis
from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.api.webhook import router as webhook_router
from app.api.runs import router as runs_router



app = FastAPI(title="CodeScope")

app.include_router(webhook_router)
app.include_router(runs_router)

@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    redis.Redis.from_url(settings.redis_url).ping()
    return {"status": "ok", "db": "ok", "redis": "ok"}