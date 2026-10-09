from datetime import UTC, datetime
from itertools import product
from uuid import uuid4

import pytest

from app.domain.applications import ApplicationState
from app.domain.enums import ALL_APP_STATUSES, AppStatus
from app.domain.state_machine import (
    TERMINAL,
    TRANSITIONS,
    USER_ONLY_TARGETS,
    InvalidTransition,
    can_transition,
    transition,
)

# Written out independently of TRANSITIONS so a typo in the table fails a test.
EXPECTED_ALLOWED: set[tuple[AppStatus, AppStatus]] = {
    ("queued", "applied"),
    ("queued", "withdrawn"),
    ("queued", "archived"),
    ("applied", "next_steps"),
    ("applied", "rejected"),
    ("applied", "offer"),
    ("applied", "no_response"),
    ("applied", "withdrawn"),
    ("next_steps", "next_steps"),
    ("next_steps", "rejected"),
    ("next_steps", "offer"),
    ("next_steps", "withdrawn"),
    ("no_response", "next_steps"),
    ("no_response", "rejected"),
    ("no_response", "offer"),
    ("offer", "accepted"),
    ("offer", "declined"),
}

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
ALL_PAIRS = list(product(ALL_APP_STATUSES, ALL_APP_STATUSES))


def app(status: AppStatus, stage: str | None = None) -> ApplicationState:
    return ApplicationState(id=uuid4(), status=status, stage=stage)


def test_table_covers_every_status() -> None:
    assert set(TRANSITIONS) == set(ALL_APP_STATUSES)


def test_terminal_states() -> None:
    assert TERMINAL == {"rejected", "withdrawn", "accepted", "declined", "archived"}


@pytest.mark.parametrize(("frm", "to"), ALL_PAIRS)
def test_every_pair_matches_expected_table(frm: AppStatus, to: AppStatus) -> None:
    allowed = (frm, to) in EXPECTED_ALLOWED
    assert can_transition(frm, to) is allowed

    stage = "onsite" if to == "next_steps" else None
    current = app(frm, stage="phone_screen" if frm == "next_steps" else None)
    if allowed:
        event = transition(current, to, actor="user", stage=stage, now=NOW)
        assert (event.from_status, event.to_status) == (frm, to)
        assert event.application_id == current.id
        assert event.occurred_at == NOW
        assert event.override is False
    else:
        with pytest.raises(InvalidTransition):
            transition(current, to, actor="user", stage=stage, now=NOW)


@pytest.mark.parametrize(("frm", "to"), sorted(EXPECTED_ALLOWED))
def test_non_user_actors_cannot_reach_user_only_targets(frm: AppStatus, to: AppStatus) -> None:
    stage = "onsite" if to == "next_steps" else None
    current = app(frm, stage="phone_screen" if frm == "next_steps" else None)
    for actor in ("system", "email"):
        if to in USER_ONLY_TARGETS:
            with pytest.raises(InvalidTransition, match="only the user"):
                transition(current, to, actor=actor, stage=stage, now=NOW)
        else:
            assert transition(current, to, actor=actor, stage=stage, now=NOW).actor == actor


def test_email_can_never_accept_an_offer() -> None:
    with pytest.raises(InvalidTransition):
        transition(app("offer"), "accepted", actor="email")


class TestStageChange:
    def test_new_stage_is_allowed(self) -> None:
        event = transition(
            app("next_steps", "phone_screen"), "next_steps", actor="email", stage="onsite", now=NOW
        )
        assert event.stage == "onsite"

    @pytest.mark.parametrize("stage", [None, "", "phone_screen"])
    def test_missing_or_same_stage_is_rejected(self, stage: str | None) -> None:
        with pytest.raises(InvalidTransition, match="new stage"):
            transition(app("next_steps", "phone_screen"), "next_steps", actor="user", stage=stage)

    def test_entering_next_steps_without_stage_is_allowed(self) -> None:
        assert transition(app("applied"), "next_steps", actor="email").stage is None


class TestOverride:
    @pytest.mark.parametrize(("frm", "to"), [p for p in ALL_PAIRS if p[0] != p[1]])
    def test_user_override_allows_any_change(self, frm: AppStatus, to: AppStatus) -> None:
        event = transition(app(frm), to, actor="user", override=True, reason="misclassified")
        assert event.override is True
        assert event.reason == "misclassified"

    @pytest.mark.parametrize("actor", ["system", "email"])
    def test_override_requires_user(self, actor: str) -> None:
        with pytest.raises(InvalidTransition, match="override requires"):
            transition(app("rejected"), "next_steps", actor=actor, override=True)  # type: ignore[arg-type]

    def test_override_to_identical_state_is_rejected(self) -> None:
        with pytest.raises(InvalidTransition, match="no-op"):
            transition(app("rejected"), "rejected", actor="user", override=True)

    def test_override_same_status_new_stage_is_allowed(self) -> None:
        event = transition(
            app("next_steps", "a"), "next_steps", actor="user", stage="b", override=True
        )
        assert event.stage == "b"


def test_default_timestamp_is_utc_now() -> None:
    before = datetime.now(UTC)
    event = transition(app("queued"), "applied", actor="system")
    assert before <= event.occurred_at <= datetime.now(UTC)
    assert event.occurred_at.tzinfo is UTC
