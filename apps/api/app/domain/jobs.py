from datetime import datetime
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.domain.enums import ATS, CompInterval, EmploymentType, WorkplaceType


class Compensation(BaseModel):
    model_config = ConfigDict(frozen=True)

    min: float | None = None
    max: float | None = None
    currency: str | None = None
    interval: CompInterval = "unknown"


class JobPosting(BaseModel):
    """What every ATS adapter returns. Adapters map fields; parsing helpers live in ingestion."""

    source: ATS
    source_token: str
    external_id: str
    title: str
    department: str | None = None
    description_html: str | None = None
    description_text: str
    location_raw: str | None = None
    locations: list[str] = Field(default_factory=list)
    workplace_type: WorkplaceType = "unknown"
    employment_type: EmploymentType = "unknown"
    compensation: Compensation | None = None
    apply_url: HttpUrl
    canonical_url: HttpUrl
    posted_at: datetime | None = None
    source_updated_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class SourceError(Exception):
    """Base class for errors raised by ATS adapters."""


class SourceNotFound(SourceError):
    """The board token doesn't exist (HTTP 404). Not retried."""


class SourceTransientError(SourceError):
    """Rate limit, 5xx, timeout or network failure. The caller retries."""


class JobSource(Protocol):
    ats: ATS

    async def fetch_jobs(self, token: str, client: httpx.AsyncClient) -> list[JobPosting]:
        """Return every listed job on the board. Raises SourceNotFound / SourceTransientError.

        A single malformed job is skipped and logged; it never fails the batch.
        """
        ...

    async def exists(self, token: str, client: httpx.AsyncClient) -> bool:
        """True if the board token resolves on this ATS. Raises SourceTransientError."""
        ...
