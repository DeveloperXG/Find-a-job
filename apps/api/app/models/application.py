import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import Actor, AppPriority, AppStatus
from app.models.base import Base, TimestampMixin, UUIDMixin, literal_enum


class Application(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "applications"

    job_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("jobs.id"), unique=True)
    resume_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("resumes.id"))
    status: Mapped[str] = mapped_column(
        literal_enum(AppStatus, "app_status"), server_default="queued"
    )
    stage: Mapped[str | None] = mapped_column(sa.Text)
    priority: Mapped[str] = mapped_column(
        literal_enum(AppPriority, "app_priority"), server_default="normal"
    )
    applied_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_status_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    notes: Mapped[str | None] = mapped_column(sa.Text)


class ApplicationEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "application_events"

    application_id: Mapped[uuid.UUID] = mapped_column(
        sa.ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(literal_enum(AppStatus, "event_from_status"))
    to_status: Mapped[str] = mapped_column(literal_enum(AppStatus, "event_to_status"))
    stage: Mapped[str | None] = mapped_column(sa.Text)
    actor: Mapped[str] = mapped_column(literal_enum(Actor, "actor"))
    reason: Mapped[str | None] = mapped_column(sa.Text)
    override: Mapped[bool] = mapped_column(server_default=sa.false())
    payload: Mapped[dict[str, Any]] = mapped_column(server_default=sa.text("'{}'::jsonb"))
