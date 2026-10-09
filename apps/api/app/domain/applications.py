from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import Actor, AppPriority, AppStatus


class ApplicationState(BaseModel):
    """The slice of an application the state machine needs; built from the ORM row."""

    model_config = ConfigDict(frozen=True)

    id: UUID
    status: AppStatus
    stage: str | None = None
    priority: AppPriority = "normal"


class ApplicationEvent(BaseModel):
    """An auditable status change. The service persists it to `application_events`."""

    model_config = ConfigDict(frozen=True)

    application_id: UUID
    from_status: AppStatus
    to_status: AppStatus
    stage: str | None = None
    actor: Actor
    reason: str | None = None
    override: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime
