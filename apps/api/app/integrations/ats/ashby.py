"""Ashby public job-board API: https://api.ashbyhq.com/posting-api/job-board/{token}."""

from typing import Any

import httpx
import structlog
from bs4 import BeautifulSoup

from app.domain.enums import ATS, CompInterval, EmploymentType, WorkplaceType
from app.domain.jobs import Compensation, JobPosting, SourceError
from app.integrations.ats.base import get, json_body, parse_iso

log = structlog.get_logger(__name__)

API = "https://api.ashbyhq.com/posting-api/job-board"

_WORKPLACE: dict[str, WorkplaceType] = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
}
_EMPLOYMENT: dict[str, EmploymentType] = {
    "fulltime": "full_time",
    "parttime": "part_time",
    "intern": "internship",
    "contract": "contract",
    "temporary": "contract",
}
# Ashby intervals look like "1 YEAR" / "1 HOUR"; anything else (e.g. "NONE", "1 MONTH") is unknown.
_INTERVAL: dict[str, CompInterval] = {"1 YEAR": "year", "1 HOUR": "hour"}

_DROPPED_FROM_RAW = ("descriptionHtml", "descriptionPlain")


def _compensation(job: dict[str, Any]) -> Compensation | None:
    comp = job.get("compensation")
    if not isinstance(comp, dict):
        return None
    # `summaryComponents` rolls up the tiers; fall back to the first tier's components.
    components = comp.get("summaryComponents")
    if not components:
        tiers = comp.get("compensationTiers") or []
        components = tiers[0].get("components") if tiers else []
    for component in components or []:
        if component.get("compensationType") != "Salary":  # skip equity, bonus, commission
            continue
        low, high = component.get("minValue"), component.get("maxValue")
        if low is None and high is None:
            continue
        return Compensation(
            min=low,
            max=high,
            currency=component.get("currencyCode"),
            interval=_INTERVAL.get(str(component.get("interval")), "unknown"),
        )
    return None


def _locations(job: dict[str, Any]) -> list[str]:
    names = [job.get("location")]
    names += [
        secondary.get("location")
        for secondary in job.get("secondaryLocations") or []
        if isinstance(secondary, dict)
    ]
    seen: dict[str, None] = {}  # de-duplicate, keeping order
    for name in names:
        if isinstance(name, str) and name.strip():
            seen.setdefault(name.strip())
    return list(seen)


def _to_posting(token: str, job: dict[str, Any]) -> JobPosting:
    description_html = job.get("descriptionHtml") or None
    description_text = job.get("descriptionPlain") or ""
    if not description_text and description_html:
        # Minimal mapping-level text; ingestion re-derives clean text with html_to_text (S1-07).
        description_text = BeautifulSoup(description_html, "lxml").get_text("\n", strip=True)
    locations = _locations(job)
    workplace = _WORKPLACE.get(str(job.get("workplaceType", "")).strip().lower(), "unknown")
    return JobPosting(
        source="ashby",
        source_token=token,
        external_id=str(job["id"]),
        title=job["title"].strip(),  # recorded titles can carry stray leading whitespace
        department=job.get("department") or None,
        description_html=description_html,
        description_text=description_text,
        location_raw=job.get("location") or None,
        locations=locations,
        workplace_type=workplace,
        employment_type=_EMPLOYMENT.get(str(job.get("employmentType", "")).lower(), "unknown"),
        compensation=_compensation(job),
        apply_url=job["applyUrl"],
        canonical_url=job["jobUrl"],
        posted_at=parse_iso(job.get("publishedAt")),
        raw={k: v for k, v in job.items() if k not in _DROPPED_FROM_RAW},
    )


class AshbySource:
    ats: ATS = "ashby"

    async def fetch_jobs(self, token: str, client: httpx.AsyncClient) -> list[JobPosting]:
        response = await get(client, f"{API}/{token}?includeCompensation=true")
        body = json_body(response)
        jobs = body.get("jobs") if isinstance(body, dict) else None
        if not isinstance(jobs, list):
            raise SourceError(f"ashby board {token!r}: unexpected response shape")

        postings: list[JobPosting] = []
        for job in jobs:
            try:
                if job.get("isListed") is False:  # unlisted jobs are not public postings
                    continue
                postings.append(_to_posting(token, job))
            except Exception as exc:  # one bad job must never fail the batch (AGENTS.md 9a)
                # Log only identifiers: never posting content.
                log.warning(
                    "skipping malformed job",
                    ats="ashby",
                    token=token,
                    external_id=job.get("id") if isinstance(job, dict) else None,
                    error=type(exc).__name__,
                )
        return postings

    async def exists(self, token: str, client: httpx.AsyncClient) -> bool:
        # Ashby has no board-only endpoint; the job-board listing itself 404s for unknown tokens.
        response = await get(client, f"{API}/{token}", ok_404=True)
        return response.status_code == 200
