"""Lever public postings API: https://api.lever.co/v0/postings/{token}?mode=json (EU host too)."""

from datetime import UTC, datetime
from typing import Any, Literal

import httpx
import structlog
from bs4 import BeautifulSoup

from app.domain.enums import ATS, CompInterval, WorkplaceType
from app.domain.jobs import Compensation, JobPosting, SourceError, SourceNotFound
from app.integrations.ats.base import get, json_body

log = structlog.get_logger(__name__)

Region = Literal["us", "eu"]
# Tried in order: a company lives on exactly one, and the US host 404s for EU-hosted boards.
REGIONS: tuple[tuple[Region, str], ...] = (
    ("us", "https://api.lever.co/v0/postings"),
    ("eu", "https://api.eu.lever.co/v0/postings"),
)

_WORKPLACE: dict[str, WorkplaceType] = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
}
# Lever also has month/week/bonus intervals; those can't be normalised to year/hour, so "unknown".
_INTERVAL: dict[str, CompInterval] = {"per-year-salary": "year", "per-hour-wage": "hour"}
# Large body fields are stored separately (description_html / description_text), not in `raw`.
_BODY_KEYS = frozenset(
    {
        "description",
        "descriptionPlain",
        "descriptionBody",
        "descriptionBodyPlain",
        "opening",
        "openingPlain",
        "additional",
        "additionalPlain",
        "lists",
    }
)


def _epoch_ms(value: object) -> datetime | None:
    # Lever's `createdAt` is epoch *milliseconds*; bool is an int subclass, so exclude it.
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _compensation(job: dict[str, Any]) -> Compensation | None:
    salary = job.get("salaryRange")
    if not isinstance(salary, dict) or (salary.get("min") is None and salary.get("max") is None):
        return None
    return Compensation(
        min=salary.get("min"),
        max=salary.get("max"),
        currency=salary.get("currency"),
        interval=_INTERVAL.get(str(salary.get("interval", "")).lower(), "unknown"),
    )


def _html_text(fragment: str) -> str:
    return BeautifulSoup(fragment, "lxml").get_text("\n", strip=True)


def _description(job: dict[str, Any]) -> tuple[str | None, str]:
    """Join the intro, the `lists[]` sections (requirements etc.) and the closing text."""
    html_parts: list[str] = []
    text_parts: list[str] = []
    if job.get("description"):
        html_parts.append(job["description"])
    if job.get("descriptionPlain"):
        text_parts.append(job["descriptionPlain"].strip())
    for section in job.get("lists") or []:
        heading, content = section.get("text") or "", section.get("content") or ""
        html_parts.append(f"<h3>{heading}</h3><ul>{content}</ul>")
        text_parts.append("\n".join(p for p in (heading, _html_text(content)) if p))
    if job.get("additional"):
        html_parts.append(job["additional"])
    if job.get("additionalPlain"):
        text_parts.append(job["additionalPlain"].strip())
    return ("\n".join(html_parts) or None), "\n\n".join(p for p in text_parts if p)


def _to_posting(token: str, region: Region, job: dict[str, Any]) -> JobPosting:
    categories = job.get("categories") or {}
    location = categories.get("location")
    locations = categories.get("allLocations") or ([location] if location else [])
    description_html, description_text = _description(job)
    return JobPosting(
        source="lever",
        source_token=token,
        external_id=str(job["id"]),
        title=job["text"],
        department=categories.get("department") or categories.get("team"),
        description_html=description_html,
        description_text=description_text,
        location_raw=location,
        locations=locations,
        workplace_type=_WORKPLACE.get(str(job.get("workplaceType", "")).lower(), "unknown"),
        compensation=_compensation(job),
        apply_url=job["applyUrl"],
        canonical_url=job["hostedUrl"],
        posted_at=_epoch_ms(job.get("createdAt")),
        raw={**{k: v for k, v in job.items() if k not in _BODY_KEYS}, "_region": region},
    )


class LeverSource:
    ats: ATS = "lever"

    async def fetch_jobs(self, token: str, client: httpx.AsyncClient) -> list[JobPosting]:
        region, body = await self._fetch(token, client)
        if not isinstance(body, list):
            raise SourceError(f"lever board {token!r}: unexpected response shape")

        postings: list[JobPosting] = []
        for job in body:
            try:
                postings.append(_to_posting(token, region, job))
            except Exception as exc:  # one bad job must never fail the batch (AGENTS.md 9a)
                # Log only identifiers: never posting content.
                log.warning(
                    "skipping malformed job",
                    ats="lever",
                    token=token,
                    external_id=job.get("id") if isinstance(job, dict) else None,
                    error=type(exc).__name__,
                )
        return postings

    async def exists(self, token: str, client: httpx.AsyncClient) -> bool:
        for _, base in REGIONS:
            response = await get(client, f"{base}/{token}?mode=json&limit=1", ok_404=True)
            if response.status_code == 200:
                return True
        return False

    async def _fetch(self, token: str, client: httpx.AsyncClient) -> tuple[Region, Any]:
        """US first; a 404 there means "not on this region", so retry EU before giving up."""
        for region, base in REGIONS:
            try:
                response = await get(client, f"{base}/{token}?mode=json")
            except SourceNotFound:
                continue  # transient errors are not caught: they propagate for the caller to retry
            return region, json_body(response)
        raise SourceNotFound(f"lever board {token!r} not found in the US or EU region")
