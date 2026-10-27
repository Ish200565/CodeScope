import redis
from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db

app = FastAPI(title="CodeScope")

@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    redis.Redis.from_url(settings.redis_url).ping()
    return {"status": "ok", "db": "ok", "redis": "ok"}