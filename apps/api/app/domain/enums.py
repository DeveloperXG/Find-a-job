"""Shared vocabulary. Literals (not Enums) so values are plain strings in JSON, the DB and TS.

Iterate a Literal with `typing.get_args(...)`, or use the `ALL_*` tuples below.
"""

from typing import Literal, get_args

ATS = Literal["greenhouse", "lever", "ashby"]
WorkplaceType = Literal["remote", "hybrid", "onsite", "unknown"]
EmploymentType = Literal[
    "full_time", "part_time", "contract", "internship", "fellowship", "unknown"
]
Seniority = Literal[
    "intern", "new_grad", "junior", "mid", "senior", "staff_plus", "manager", "unknown"
]
RoleFamily = Literal[
    "sde", "mle", "aie", "research", "data_science", "robotics", "cv", "data_eng", "other"
]
CompInterval = Literal["year", "hour", "unknown"]

AppStatus = Literal[
    "queued",
    "applied",
    "next_steps",
    "no_response",
    "offer",
    "rejected",
    "withdrawn",
    "accepted",
    "declined",
    "archived",
]
AppPriority = Literal["normal", "high"]
Actor = Literal["user", "system", "email"]

CompanyPriority = Literal["low", "normal", "high"]
CompanyStatus = Literal["active", "inactive", "invalid"]
JobStatus = Literal["open", "closed"]
FilterStatus = Literal["pending", "passed", "rejected"]
UserState = Literal["none", "saved", "dismissed"]
RecommendedAction = Literal["apply", "maybe", "skip"]
MatchStatus = Literal["ok", "failed"]
ResumeKind = Literal["master", "variant"]
WorkflowRunStatus = Literal["running", "ok", "partial", "failed"]

NotificationChannel = Literal["inapp", "push", "email"]
NotificationPriority = Literal["low", "default", "high"]

ALL_ATS: tuple[ATS, ...] = get_args(ATS)
ALL_APP_STATUSES: tuple[AppStatus, ...] = get_args(AppStatus)
ALL_ROLE_FAMILIES: tuple[RoleFamily, ...] = get_args(RoleFamily)
ALL_SENIORITIES: tuple[Seniority, ...] = get_args(Seniority)
ALL_CHANNELS: tuple[NotificationChannel, ...] = get_args(NotificationChannel)
