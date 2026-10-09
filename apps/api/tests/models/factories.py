"""Builders for valid rows. All data is fake (example.com, invented names)."""

import itertools
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Application,
    ApplicationEvent,
    Company,
    Job,
    JobMatch,
    JobSource,
    LLMCall,
    Notification,
    Profile,
    Resume,
    WorkflowRun,
)

_seq = itertools.count(1)


def _n() -> int:
    return next(_seq)


async def add(session: AsyncSession, row: Any) -> Any:
    session.add(row)
    await session.flush()
    return row


async def make_company(session: AsyncSession, **kw: Any) -> Company:
    return await add(session, Company(name=kw.pop("name", f"Acme {_n()}"), **kw))


async def make_source(
    session: AsyncSession, company: Company | None = None, **kw: Any
) -> JobSource:
    company = company or await make_company(session)
    kw.setdefault("ats", "greenhouse")
    kw.setdefault("token", f"acme-{_n()}")
    return await add(session, JobSource(company_id=company.id, **kw))


async def make_job(session: AsyncSession, source: JobSource | None = None, **kw: Any) -> Job:
    source = source or await make_source(session)
    n = _n()
    defaults: dict[str, Any] = {
        "external_id": f"ext-{n}",
        "title": "Junior Software Engineer",
        "title_normalized": "junior software engineer",
        "role_family": "sde",
        "seniority": "junior",
        "description_text": "Build things.",
        "content_hash": "a" * 64,
        "fingerprint": "b" * 64,
        "workplace_type": "remote",
        "employment_type": "full_time",
        "apply_url": f"https://example.com/jobs/{n}/apply",
        "canonical_url": f"https://example.com/jobs/{n}",
    }
    return await add(
        session, Job(source_id=source.id, company_id=source.company_id, **{**defaults, **kw})
    )


async def make_match(session: AsyncSession, job: Job | None = None, **kw: Any) -> JobMatch:
    job = job or await make_job(session)
    defaults: dict[str, Any] = {
        "content_hash": job.content_hash,
        "profile_version": 1,
        "rubric_version": "score_v1",
        "model": "test-model",
        "score": 80,
        "status": "ok",
    }
    return await add(session, JobMatch(job_id=job.id, **{**defaults, **kw}))


async def make_resume(session: AsyncSession, **kw: Any) -> Resume:
    defaults: dict[str, Any] = {"kind": "master", "name": "Master", "content": {"basics": {}}}
    return await add(session, Resume(**{**defaults, **kw}))


async def make_application(session: AsyncSession, job: Job | None = None, **kw: Any) -> Application:
    job = job or await make_job(session)
    return await add(session, Application(job_id=job.id, **kw))


async def make_event(session: AsyncSession, app: Application, **kw: Any) -> ApplicationEvent:
    defaults: dict[str, Any] = {"to_status": "queued", "actor": "system"}
    return await add(session, ApplicationEvent(application_id=app.id, **{**defaults, **kw}))


async def make_notification(session: AsyncSession, **kw: Any) -> Notification:
    defaults: dict[str, Any] = {
        "kind": "application.status",
        "title": "Moved to next steps",
        "body": "Example body",
        "dedupe_key": f"key-{_n()}",
    }
    return await add(session, Notification(**{**defaults, **kw}))


async def make_workflow_run(session: AsyncSession, **kw: Any) -> WorkflowRun:
    return await add(session, WorkflowRun(kind=kw.pop("kind", "discovery"), **kw))


async def make_llm_call(session: AsyncSession, **kw: Any) -> LLMCall:
    defaults: dict[str, Any] = {"task": "score", "model": "test-model"}
    return await add(session, LLMCall(**{**defaults, **kw}))


async def make_profile(session: AsyncSession, **kw: Any) -> Profile:
    return await add(session, Profile(**kw))
