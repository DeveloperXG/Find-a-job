from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Profile(TimestampMixin, Base):
    """Single-row table (id = 1). Every save increments `version`."""

    __tablename__ = "profile"
    __table_args__ = (sa.CheckConstraint("id = 1", name="single_row"),)

    id: Mapped[int] = mapped_column(primary_key=True, server_default="1")
    version: Mapped[int] = mapped_column(server_default="1")
    candidate: Mapped[dict[str, Any]] = mapped_column(server_default=sa.text("'{}'::jsonb"))
    preferences: Mapped[dict[str, Any]] = mapped_column(server_default=sa.text("'{}'::jsonb"))
