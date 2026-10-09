from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApplicationEvent, Job, LLMCall, Profile
from tests.models import factories as f


async def assert_integrity_error(session: AsyncSession, row: Any) -> None:
    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            session.add(row)
            await session.flush()


# --- unique constraints (the five named in the story's test plan) -------------------------


async def test_job_sources_ats_token_unique(db_session: AsyncSession) -> None:
    first = await f.make_source(db_session, ats="ashby", token="dup")
    other = await f.make_company(db_session)
    from app.models import JobSource

    await assert_integrity_error(
        db_session, JobSource(company_id=other.id, ats=first.ats, token="dup")
    )
    # same token on another ATS is fine
    await f.make_source(db_session, other, ats="lever", token="dup")


async def test_jobs_source_external_id_unique(db_session: AsyncSession) -> None:
    job = await f.make_job(db_session, external_id="X1")
    clone = Job(
        source_id=job.source_id,
        company_id=job.company_id,
        external_id="X1",
        title="t",
        title_normalized="t",
        role_family="sde",
        seniority="junior",
        description_text="d",
        content_hash="c" * 64,
        fingerprint="d" * 64,
        workplace_type="remote",
        employment_type="full_time",
        apply_url="https://example.com/a",
        canonical_url="https://example.com/a",
    )
    await assert_integrity_error(db_session, clone)


async def test_job_matches_cache_key_unique(db_session: AsyncSession) -> None:
    from app.models import JobMatch

    job = await f.make_job(db_session)
    await f.make_match(db_session, job)
    dup = JobMatch(
        job_id=job.id,
        content_hash=job.content_hash,
        profile_version=1,
        rubric_version="score_v1",
        model="test-model",
        status="failed",
    )
    await assert_integrity_error(db_session, dup)
    # changing any one component of the key is a distinct row (old matches are kept as history)
    await f.make_match(db_session, job, profile_version=2)
    await f.make_match(db_session, job, rubric_version="score_v2")
    await f.make_match(db_session, job, model="other-model")
    await f.make_match(db_session, job, content_hash="e" * 64)


async def test_applications_job_id_unique(db_session: AsyncSession) -> None:
    from app.models import Application

    app = await f.make_application(db_session)
    await assert_integrity_error(db_session, Application(job_id=app.job_id))


async def test_notifications_dedupe_key_unique(db_session: AsyncSession) -> None:
    from app.models import Notification

    await f.make_notification(db_session, dedupe_key="a:next_steps:onsite")
    await assert_integrity_error(
        db_session, Notification(kind="k", title="t", body="b", dedupe_key="a:next_steps:onsite")
    )


# --- CHECK constraints from the domain Literals -------------------------------------------


@pytest.mark.parametrize(
    ("kind", "field", "bad"),
    [
        ("company", "priority", "nope"),
        ("source", "ats", "nope"),
        ("job", "workplace_type", "nope"),
        ("job", "role_family", "nope"),
        ("job", "status", "nope"),
        ("job", "filter_status", "nope"),
        ("application", "status", "nope"),
        ("notification", "priority", "nope"),
        ("workflow", "status", "nope"),
    ],
)
async def test_enum_check_rejects_unknown_value(
    db_session: AsyncSession, kind: str, field: str, bad: str
) -> None:
    builders = {
        "company": f.make_company,
        "source": f.make_source,
        "job": f.make_job,
        "application": f.make_application,
        "notification": f.make_notification,
        "workflow": f.make_workflow_run,
    }
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await builders[kind](db_session, **{field: bad})


async def test_score_must_be_0_to_100(db_session: AsyncSession) -> None:
    job = await f.make_job(db_session)
    for bad in (-1, 101):
        with pytest.raises(IntegrityError):
            async with db_session.begin_nested():
                await f.make_match(db_session, job, score=bad, model=f"m{bad}")
    await f.make_match(db_session, job, score=0, model="lo")
    await f.make_match(db_session, job, score=100, model="hi")


async def test_profile_is_single_row(db_session: AsyncSession) -> None:
    await f.make_profile(db_session)
    await assert_integrity_error(db_session, Profile(id=2))
    await assert_integrity_error(db_session, Profile())  # id defaults to 1 -> duplicate PK


# --- relationships / referential behaviour ------------------------------------------------


async def test_foreign_keys_enforced(db_session: AsyncSession) -> None:
    import uuid

    await assert_integrity_error(
        db_session,
        ApplicationEvent(application_id=uuid.uuid4(), to_status="queued", actor="system"),
    )


async def test_deleting_application_cascades_to_events(db_session: AsyncSession) -> None:
    app = await f.make_application(db_session)
    await f.make_event(db_session, app)
    await f.make_event(db_session, app, from_status="queued", to_status="applied", actor="user")
    await db_session.delete(app)
    await db_session.flush()
    count = await db_session.scalar(select(func.count()).select_from(ApplicationEvent))
    assert count == 0


async def test_deleting_job_keeps_cost_ledger_row(db_session: AsyncSession) -> None:
    job = await f.make_job(db_session)
    call = await f.make_llm_call(db_session, job_id=job.id)
    call_id = call.id
    await f.make_match(db_session, job)
    await db_session.delete(job)
    await db_session.flush()
    db_session.expire_all()
    got = await db_session.get(LLMCall, call_id)
    assert got is not None and got.job_id is None  # ledger survives, link is cleared
