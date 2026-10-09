import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import ATS, CompanyPriority, CompanyStatus
from app.models.base import Base, TimestampMixin, UUIDMixin, literal_enum


class Company(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(sa.Text)
    website: Mapped[str | None] = mapped_column(sa.Text)
    priority: Mapped[str] = mapped_column(
        literal_enum(CompanyPriority, "company_priority"), server_default="normal"
    )
    status: Mapped[str] = mapped_column(
        literal_enum(CompanyStatus, "company_status"), server_default="active"
    )
    notes: Mapped[str | None] = mapped_column(sa.Text)


class JobSource(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "job_sources"
    __table_args__ = (sa.UniqueConstraint("ats", "token", name="uq_job_sources_ats_token"),)

    company_id: Mapped[uuid.UUID] = mapped_column(sa.ForeignKey("companies.id"))
    ats: Mapped[str] = mapped_column(literal_enum(ATS, "ats"))
    token: Mapped[str] = mapped_column(sa.Text)
    enabled: Mapped[bool] = mapped_column(server_default=sa.true())
    last_polled_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(server_default="0")
    last_error: Mapped[str | None] = mapped_column(sa.Text)
