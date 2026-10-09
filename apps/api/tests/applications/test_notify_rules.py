from uuid import UUID

import pytest

from app.applications.notify_rules import (
    ALL,
    INAPP,
    NONE,
    QUOTA_REACHED_CHANNELS,
    channels_for,
    dedupe_key,
    priority_for,
)
from app.domain.enums import AppPriority, AppStatus, NotificationChannel


@pytest.mark.parametrize(
    ("frm", "to", "priority", "expected"),
    [
        # Rejections: quiet unless it hurts
        ("queued", "rejected", "normal", INAPP),
        ("applied", "rejected", "normal", INAPP),
        ("no_response", "rejected", "normal", INAPP),
        ("applied", "rejected", "high", ALL),
        ("no_response", "rejected", "high", ALL),
        ("next_steps", "rejected", "normal", ALL),
        ("next_steps", "rejected", "high", ALL),
        ("offer", "rejected", "normal", ALL),  # rescinded offer (via user override)
        # Good news: everywhere
        ("applied", "next_steps", "normal", ALL),
        ("no_response", "next_steps", "normal", ALL),
        ("next_steps", "next_steps", "normal", ALL),
        ("applied", "offer", "normal", ALL),
        ("next_steps", "offer", "normal", ALL),
        ("no_response", "offer", "high", ALL),
        # Housekeeping
        ("queued", "applied", "normal", INAPP),
        ("applied", "no_response", "normal", NONE),
        ("applied", "no_response", "high", NONE),
        ("queued", "withdrawn", "normal", NONE),
        ("queued", "archived", "normal", NONE),
        ("offer", "accepted", "high", NONE),
        ("offer", "declined", "normal", NONE),
    ],
)
def test_rule_matrix(
    frm: AppStatus, to: AppStatus, priority: AppPriority, expected: frozenset[NotificationChannel]
) -> None:
    assert channels_for(frm, to, priority) == expected


def test_quota_reached_goes_everywhere() -> None:
    assert QUOTA_REACHED_CHANNELS == {"inapp", "push", "email"}


@pytest.mark.parametrize(
    ("to", "expected"), [("next_steps", "high"), ("offer", "high"), ("rejected", "default")]
)
def test_priority_for(to: AppStatus, expected: str) -> None:
    assert priority_for(to) == expected


def test_dedupe_key_distinguishes_stages() -> None:
    app_id = UUID("00000000-0000-0000-0000-000000000001")
    assert dedupe_key(app_id, "next_steps", "onsite") == f"{app_id}:next_steps:onsite"
    assert dedupe_key(app_id, "rejected", None) == f"{app_id}:rejected:"
    assert dedupe_key(app_id, "next_steps", "a") != dedupe_key(app_id, "next_steps", "b")
