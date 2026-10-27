#Run,StepRun
import uuid
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, Integer, String, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base

def utcnow():
    return datetime.now(timezone.utc)

class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    repo_full_name: Mapped[str] = mapped_column(String(200))
    pr_number: Mapped[int] = mapped_column(Integer)
    head_sha: Mapped[str] = mapped_column(String(40), index=True)
    installation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|succeeded|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    steps: Mapped[list["StepRun"]] = relationship(back_populates="run", cascade="all, delete-orphan")

class StepRun(Base):
    __tablename__ = "step_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    run: Mapped["Run"] = relationship(back_populates="steps")