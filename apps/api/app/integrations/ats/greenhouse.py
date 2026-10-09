"""Greenhouse public job-board API: https://boards-api.greenhouse.io/v1/boards/{token}/jobs."""

import html
from typing import Any

import httpx
import structlog
from bs4 import BeautifulSoup

from app.domain.enums import ATS, WorkplaceType
from app.domain.jobs import JobPosting, SourceError
from app.integrations.ats.base import get, json_body, parse_iso

log = structlog.get_logger(__name__)

API = "https://boards-api.greenhouse.io/v1/boards"

# Greenhouse boards expose workplace as a "Location Type" metadata field.
_WORKPLACE: dict[str, WorkplaceType] = {
    "remote": "remote",
    "hybrid": "hybrid",
    "on-site": "onsite",
    "onsite": "onsite",
    "in-office": "onsite",
}


def _workplace(job: dict[str, Any]) -> WorkplaceType:
    for item in job.get("metadata") or []:
        if str(item.get("name", "")).strip().lower() == "location type":
            return _WORKPLACE.get(str(item.get("value", "")).strip().lower(), "unknown")
    return "unknown"


def _text(description_html: str) -> str:
    # Minimal mapping-level text; ingestion re-derives clean text with html_to_text (S1-07).
    return BeautifulSoup(description_html, "lxml").get_text("\n", strip=True)


def _to_posting(token: str, job: dict[str, Any]) -> JobPosting:
    # `content` is HTML that Greenhouse has entity-escaped: unescape before parsing.
    description_html = html.unescape(job["content"]) if job.get("content") else None
    location = (job.get("location") or {}).get("name")
    departments = job.get("departments") or []
    return JobPosting(
        source="greenhouse",
        source_token=token,
        external_id=str(job["id"]),
        title=job["title"],
        department=departments[0]["name"] if departments else None,
        description_html=description_html,
        description_text=_text(description_html) if description_html else "",
        location_raw=location,
        locations=[location] if location else [],
        workplace_type=_workplace(job),
        apply_url=job["absolute_url"],
        canonical_url=job["absolute_url"],
        # The recorded API has a real publish date (`first_published`), unlike the story notes.
        posted_at=parse_iso(job.get("first_published")),
        source_updated_at=parse_iso(job.get("updated_at")),
        # Keep the payload minus the (large, already stored) description.
        raw={k: v for k, v in job.items() if k != "content"},
    )


class GreenhouseSource:
    ats: ATS = "greenhouse"

    async def fetch_jobs(self, token: str, client: httpx.AsyncClient) -> list[JobPosting]:
        response = await get(client, f"{API}/{token}/jobs?content=true")
        body = json_body(response)
        jobs = body.get("jobs") if isinstance(body, dict) else None
        if not isinstance(jobs, list):
            raise SourceError(f"greenhouse board {token!r}: unexpected response shape")

        postings: list[JobPosting] = []
        for job in jobs:
            try:
                postings.append(_to_posting(token, job))
            except Exception as exc:  # one bad job must never fail the batch (AGENTS.md 9a)
                # Log only identifiers: never posting content.
                log.warning(
                    "skipping malformed job",
                    ats="greenhouse",
                    token=token,
                    external_id=job.get("id") if isinstance(job, dict) else None,
                    error=type(exc).__name__,
                )
        return postings

    async def exists(self, token: str, client: httpx.AsyncClient) -> bool:
        response = await get(client, f"{API}/{token}", ok_404=True)
        return response.status_code == 200
