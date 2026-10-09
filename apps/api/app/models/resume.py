import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import ResumeKind, RoleFamily
from app.models.base import Base, TimestampMixin, UUIDMixin, literal_enum


class Resume(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "resumes"

    kind: Mapped[str] = mapped_column(literal_enum(ResumeKind, "resume_kind"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(sa.ForeignKey("resumes.id"))
    master_version: Mapped[int] = mapped_column(server_default="1")
    name: Mapped[str] = mapped_column(sa.Text)
    role_family: Mapped[str | None] = mapped_column(literal_enum(RoleFamily, "resume_role_family"))
    content: Mapped[dict[str, Any]] = mapped_column()
    keyword_signature: Mapped[list[Any]] = mapped_column(server_default=sa.text("'[]'::jsonb"))
    source_job_id: Mapped[uuid.UUID | None] = mapped_column(
        sa.ForeignKey("jobs.id", ondelete="SET NULL")
    )
    model: Mapped[str | None] = mapped_column(sa.Text)
    archived: Mapped[bool] = mapped_column(server_default=sa.false())
