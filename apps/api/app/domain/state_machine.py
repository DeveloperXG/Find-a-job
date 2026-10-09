"""Application status transitions. Pure: no I/O. The only sanctioned way to change a status."""

from datetime import UTC, datetime
from types import MappingProxyType

from app.domain.applications import ApplicationEvent, ApplicationState
from app.domain.enums import Actor, AppStatus

TRANSITIONS: MappingProxyType[AppStatus, frozenset[AppStatus]] = MappingProxyType(
    {
        "queued": frozenset({"applied", "withdrawn", "archived"}),
        "applied": frozenset({"next_steps", "rejected", "offer", "no_response", "withdrawn"}),
        "next_steps": frozenset({"next_steps", "rejected", "offer", "withdrawn"}),
        "no_response": frozenset({"next_steps", "rejected", "offer"}),
        "offer": frozenset({"accepted", "declined"}),
        "rejected": frozenset(),
        "withdrawn": frozenset(),
        "accepted": frozenset(),
        "declined": frozenset(),
        "archived": frozenset(),
    }
)

TERMINAL: frozenset[AppStatus] = frozenset(s for s, targets in TRANSITIONS.items() if not targets)

# Decisions only the user can make. An email classifier or a workflow must never accept an offer.
USER_ONLY_TARGETS: frozenset[AppStatus] = frozenset(
    {"withdrawn", "accepted", "declined", "archived"}
)


class InvalidTransition(ValueError):
    pass


def can_transition(from_status: AppStatus, to_status: AppStatus) -> bool:
    return to_status in TRANSITIONS[from_status]


def transition(
    app: ApplicationState,
    to: AppStatus,
    *,
    actor: Actor,
    stage: str | None = None,
    reason: str | None = None,
    override: bool = False,
    now: datetime | None = None,
) -> ApplicationEvent:
    """Validate a status change and return the event to persist. Raises InvalidTransition.

    - `next_steps -> next_steps` is a stage change and requires a new, different `stage`.
    - `override=True` allows any change (to fix a misclassification) but only for actor="user".
    """
    if override:
        if actor != "user":
            raise InvalidTransition(f"override requires actor='user', got {actor!r}")
        if to == app.status and stage == app.stage:
            raise InvalidTransition(f"override to the current state ({to!r}) is a no-op")
    else:
        if not can_transition(app.status, to):
            raise InvalidTransition(f"{app.status!r} -> {to!r} is not allowed")
        if to in USER_ONLY_TARGETS and actor != "user":
            raise InvalidTransition(f"only the user may move an application to {to!r}")
        if app.status == "next_steps" and to == "next_steps" and (not stage or stage == app.stage):
            raise InvalidTransition("next_steps -> next_steps requires a new stage")

    return ApplicationEvent(
        application_id=app.id,
        from_status=app.status,
        to_status=to,
        stage=stage,
        actor=actor,
        reason=reason,
        override=override,
        occurred_at=now or datetime.now(UTC),
    )
