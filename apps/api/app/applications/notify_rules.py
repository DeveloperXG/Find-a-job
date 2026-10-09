"""Who hears about a status change, on which channels. Single source of truth for the rule matrix.

| Transition                                         | Channels               |
|----------------------------------------------------|------------------------|
| -> rejected from queued/applied/no_response        | inapp                  |
| -> rejected with priority=high                     | inapp, push, email     |
| -> rejected from next_steps or offer               | inapp, push, email     |
| -> next_steps (incl. a stage change)               | inapp, push, email     |
| -> offer                                           | inapp, push, email     |
| -> applied                                         | inapp                  |
| -> no_response                                     | none (daily digest)    |
| -> withdrawn / accepted / declined / archived      | none (user's own act)  |
| daily quota reached (Phase 3)                      | inapp, push, email     |
"""

from uuid import UUID

from app.domain.enums import AppPriority, AppStatus, NotificationChannel, NotificationPriority

ALL: frozenset[NotificationChannel] = frozenset({"inapp", "push", "email"})
INAPP: frozenset[NotificationChannel] = frozenset({"inapp"})
NONE: frozenset[NotificationChannel] = frozenset()

QUOTA_REACHED_CHANNELS = ALL


def channels_for(
    from_status: AppStatus, to_status: AppStatus, priority: AppPriority
) -> frozenset[NotificationChannel]:
    if to_status == "rejected":
        if priority == "high" or from_status in ("next_steps", "offer"):
            return ALL
        return INAPP
    if to_status in ("next_steps", "offer"):
        return ALL
    if to_status == "applied":
        return INAPP
    return NONE


def priority_for(to_status: AppStatus) -> NotificationPriority:
    return "high" if to_status in ("next_steps", "offer") else "default"


def dedupe_key(application_id: UUID, to_status: AppStatus, stage: str | None) -> str:
    return f"{application_id}:{to_status}:{stage or ''}"
