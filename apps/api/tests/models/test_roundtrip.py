from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Application, Company, Job, JobMatch, JobSource, Notification, Profile, Resume
from tests.models import factories as f


async def reload[T](session: AsyncSession, row: T) -> T:
    """Re-select the row from the database, bypassing the identity map."""
    model: Any = type(row)
    pk = row.id  # type: ignore[attr-defined]
    result = await session.execute(
        select(model).where(model.id == pk).execution_options(populate_existing=True)
    )
    return result.scalar_one()  # type: ignore[no-any-return]


async def test_company(db_session: AsyncSession) -> None:
    row = await f.make_company(db_session, name="Globex", website="https://example.com")
    got = await reload(db_session, row)
    assert isinstance(got, Company)
    assert (got.name, got.priority, got.status) == ("Globex", "normal", "active")
    assert got.created_at.tzinfo is not None and got.updated_at is not None
    assert got.id is not None


async def test_job_source(db_session: AsyncSession) -> None:
    got = await reload(db_session, await f.make_source(db_session, ats="lever", token="globex"))
    assert isinstance(got, JobSource)
    assert (got.ats, got.token, got.enabled, got.consecutive_failures) == (
        "lever",
        "globex",
        True,
        0,
    )
    assert got.last_polled_at is None and got.last_error is None


async def test_job(db_session: AsyncSession) -> None:
    posted = datetime(2026, 10, 1, tzinfo=UTC)
    row = await f.make_job(
        db_session,
        locations=["Austin, TX", "Remote - US"],
        comp_min=60000.0,
        comp_max=80000.0,
        comp_currency="USD",
        comp_interval="year",
        posted_at=posted,
        raw={"id": 1, "nested": {"a": [1, 2]}},
    )
    got = await reload(db_session, row)
    assert isinstance(got, Job)
    assert got.locations == ["Austin, TX", "Remote - US"]
    assert got.raw == {"id": 1, "nested": {"a": [1, 2]}}
    assert (got.comp_min, got.comp_max, got.comp_interval) == (60000.0, 80000.0, "year")
    assert got.posted_at == posted
    assert (got.status, got.filter_status, got.user_state) == ("open", "pending", "none")
    assert got.filter_reasons == [] and got.closed_at is None
    assert got.first_seen_at.tzinfo is not None and got.last_seen_at is not None


async def test_job_match(db_session: AsyncSession) -> None:
    row = await f.make_match(
        db_session,
        prescore=0.42,
        subscores={"technical": 30, "experience": 20, "projects": 10, "preferences": 10},
        matched_skills=["python"],
        required_skills=["python", "sql"],
        missing_requirements=["kubernetes"],
        recommended_action="apply",
        reasoning="Good fit.",
    )
    got = await reload(db_session, row)
    assert isinstance(got, JobMatch)
    assert (got.score, got.status, got.recommended_action) == (80, "ok", "apply")
    assert got.subscores["technical"] == 30
    assert got.required_skills == ["python", "sql"]


async def test_profile(db_session: AsyncSession) -> None:
    await f.make_profile(db_session, candidate={"skills": ["python"]})
    result = await db_session.execute(select(Profile).execution_options(populate_existing=True))
    got = result.scalar_one()
    assert (got.id, got.version) == (1, 1)
    assert got.candidate == {"skills": ["python"]} and got.preferences == {}


async def test_resume_with_parent(db_session: AsyncSession) -> None:
    master = await f.make_resume(db_session)
    job = await f.make_job(db_session)
    variant = await f.make_resume(
        db_session,
        kind="variant",
        parent_id=master.id,
        name="Tailored",
        role_family="sde",
        keyword_signature=["python", "sql"],
        source_job_id=job.id,
        model="test-model",
    )
    got = await reload(db_session, variant)
    assert isinstance(got, Resume)
    assert (got.kind, got.parent_id, got.master_version, got.archived) == (
        "variant",
        master.id,
        1,
        False,
    )
    assert got.keyword_signature == ["python", "sql"] and got.source_job_id == job.id


async def test_application_and_event(db_session: AsyncSession) -> None:
    app = await f.make_application(db_session)
    event = await f.make_event(db_session, app, from_status=None, to_status="queued")
    got = await reload(db_session, app)
    assert isinstance(got, Application)
    assert (got.status, got.priority, got.stage, got.applied_at) == ("queued", "normal", None, None)
    assert got.last_status_at.tzinfo is not None
    got_event = await reload(db_session, event)
    assert (got_event.to_status, got_event.actor, got_event.override) == ("queued", "system", False)
    assert got_event.payload == {}


async def test_notification(db_session: AsyncSession) -> None:
    got = await reload(
        db_session, await f.make_notification(db_session, channels=["inapp", "push"])
    )
    assert isinstance(got, Notification)
    assert (got.priority, got.channels, got.delivery, got.read_at) == (
        "default",
        ["inapp", "push"],
        {},
        None,
    )


async def test_workflow_run(db_session: AsyncSession) -> None:
    got = await reload(db_session, await f.make_workflow_run(db_session, stats={"new": 3}))
    assert (got.kind, got.status, got.stats) == ("discovery", "running", {"new": 3})
    assert got.started_at.tzinfo is not None and got.finished_at is None


async def test_llm_call_keeps_cost_precision(db_session: AsyncSession) -> None:
    job = await f.make_job(db_session)
    row = await f.make_llm_call(
        db_session, job_id=job.id, input_tokens=3000, cost_usd=Decimal("0.001234")
    )
    got = await reload(db_session, row)
    assert got.cost_usd == Decimal("0.001234")
    assert (got.cached_input_tokens, got.output_tokens, got.ok) == (0, 0, True)
