from typing import Protocol

from pydantic import BaseModel, ConfigDict

from app.domain.enums import NotificationChannel, NotificationPriority


class Notification(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    title: str
    body: str
    link: str | None = None
    priority: NotificationPriority = "default"
    dedupe_key: str


class Notifier(Protocol):
    channel: NotificationChannel

    async def send(self, n: Notification) -> None:
        """Deliver one notification. Raise on failure; the dispatcher records it and moves on."""
        ...
