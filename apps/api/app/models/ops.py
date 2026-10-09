import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import NotificationPriority, WorkflowRunStatus
from app.models.base import Base, TimestampMixin, UUIDMixin, literal_enum


class Notification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    kind: Mapped[str] = mapped_column(sa.Text)
    title: Mapped[str] = mapped_column(sa.Text)
    body: Mapped[str] = mapped_column(sa.Text)
    link: Mapped[str | None] = mapped_column(sa.Text)
    priority: Mapped[str] = mapped_column(
        literal_enum(NotificationPriority, "notification_priority"), server_default="default"
    )
    channels: Mapped[list[Any]] = mapped_column(server_default=sa.text("'[]'::jsonb"))
    delivery: Mapped[dict[str, Any]] = mapped_column(server_default=sa.text("'{}'::jsonb"))
    read_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    dedupe_key: Mapped[str] = mapped_column(sa.Text, unique=True)


class WorkflowRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workflow_runs"

    kind: Mapped[str] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(
        literal_enum(WorkflowRunStatus, "workflow_run_status"), server_default="running"
    )
    started_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    stats: Mapped[dict[str, Any]] = mapped_column(server_default=sa.text("'{}'::jsonb"))
    error: Mapped[str | None] = mapped_column(sa.Text)


class LLMCall(UUIDMixin, TimestampMixin, Base):
    """Cost ledger: one row per model call (BudgetGuard sums `cost_usd` per day)."""

    __tablename__ = "llm_calls"

    task: Mapped[str] = mapped_column(sa.Text)
    model: Mapped[str] = mapped_column(sa.Text)
    input_tokens: Mapped[int] = mapped_column(server_default="0")
    cached_input_tokens: Mapped[int] = mapped_column(server_default="0")
    output_tokens: Mapped[int] = mapped_column(server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(sa.Numeric(10, 6), server_default="0")
    job_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("jobs.id", ondelete="SET NULL"))
    ok: Mapped[bool] = mapped_column(server_default=sa.true())
