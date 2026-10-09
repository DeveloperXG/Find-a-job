import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import (
    CompInterval,
    EmploymentType,
    FilterStatus,
    JobStatus,
    MatchStatus,
    RecommendedAction,
    RoleFamily,
    Seniority,
    UserState,
    WorkplaceType,
)
from app.models.base import Base, TimestampMixin, UUIDMixin, literal_enum


class Job(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        sa.UniqueConstraint("source_id", "external_id", name="uq_jobs_source_id_external_id"),
        sa.Index("ix_jobs_fingerprint", "fingerprint"),
        sa.Index("ix_jobs_status_filter_status", "status", "filter_status"),
        sa.Index("ix_jobs_first_seen_at", "first_seen_at"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("job_sources.id"))
    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("companies.id"))
    external_id: Mapped[str] = mapped_column(sa.Text)
    title: Mapped[str] = mapped_column(sa.Text)
    title_normalized: Mapped[str] = mapped_column(sa.Text)
    role_family: Mapped[str] = mapped_column(literal_enum(RoleFamily, "role_family"))
    seniority: Mapped[str] = mapped_column(literal_enum(Seniority, "seniority"))
    department: Mapped[str | None] = mapped_column(sa.Text)
    description_text: Mapped[str] = mapped_column(sa.Text)
    description_html: Mapped[str | None] = mapped_column(sa.Text)
    content_hash: Mapped[str] = mapped_column(sa.String(64))
    fingerprint: Mapped[str] = mapped_column(sa.String(64))
    location_raw: Mapped[str | None] = mapped_column(sa.Text)
    locations: Mapped[list[Any]] = mapped_column(server_default=sa.text("'[]'::jsonb"))
    workplace_type: Mapped[str] = mapped_column(literal_enum(WorkplaceType, "workplace_type"))
    employment_type: Mapped[str] = mapped_column(literal_enum(EmploymentType, "employment_type"))
    comp_min: Mapped[float | None] = mapped_column(sa.Float)
    comp_max: Mapped[float | None] = mapped_column(sa.Float)
    comp_currency: Mapped[str | None] = mapped_column(sa.String(8))
    comp_interval: Mapped[str | None] = mapped_column(literal_enum(CompInterval, "comp_interval"))
    apply_url: Mapped[str] = mapped_column(sa.Text)
    canonical_url: Mapped[str] = mapped_column(sa.Text)
    posted_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        literal_enum(JobStatus, "job_status"), server_default="open"
    )
    filter_status: Mapped[str] = mapped_column(
        literal_enum(FilterStatus, "filter_status"), server_default="pending"
    )
    filter_reasons: Mapped[list[Any]] = mapped_column(server_default=sa.text("'[]'::jsonb"))
    user_state: Mapped[str] = mapped_column(
        literal_enum(UserState, "user_state"), server_default="none"
    )
    raw: Mapped[dict[str, Any]] = mapped_column(server_default=sa.text("'{}'::jsonb"))


class JobMatch(UUIDMixin, TimestampMixin, Base):
    """One scoring result. The unique key below is the scoring cache key."""

    __tablename__ = "job_matches"
    __table_args__ = (
        sa.UniqueConstraint(
            "job_id",
            "content_hash",
            "profile_version",
            "rubric_version",
            "model",
            name="uq_job_matches_cache_key",
        ),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="score_range"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("jobs.id", ondelete="CASCADE"))
    content_hash: Mapped[str] = mapped_column(sa.String(64))
    profile_version: Mapped[int]
    rubric_version: Mapped[str] = mapped_column(sa.Text)
    model: Mapped[str] = mapped_column(sa.Text)
    prescore: Mapped[float | None] = mapped_column(sa.Float)
    score: Mapped[int | None]
    subscores: Mapped[dict[str, Any]] = mapped_column(server_default=sa.text("'{}'::jsonb"))
    reasoning: Mapped[str | None] = mapped_column(sa.Text)
    matched_skills: Mapped[list[Any]] = mapped_column(server_default=sa.text("'[]'::jsonb"))
    missing_requirements: Mapped[list[Any]] = mapped_column(server_default=sa.text("'[]'::jsonb"))
    required_skills: Mapped[list[Any]] = mapped_column(server_default=sa.text("'[]'::jsonb"))
    recommended_action: Mapped[str | None] = mapped_column(
        literal_enum(RecommendedAction, "recommended_action")
    )
    status: Mapped[str] = mapped_column(literal_enum(MatchStatus, "match_status"))
    error: Mapped[str | None] = mapped_column(sa.Text)
