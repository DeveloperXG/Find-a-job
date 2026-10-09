"""Helpers shared by the ATS adapters. Adapters never touch the database."""

from datetime import UTC, datetime
from typing import Any

import httpx

from app.domain.jobs import SourceError, SourceNotFound, SourceTransientError

# AGENTS.md section 6: 10 s connect, 30 s read. Applied per request so it holds for any client.
TIMEOUT = httpx.Timeout(30.0, connect=10.0)


async def get(client: httpx.AsyncClient, url: str, *, ok_404: bool = False) -> httpx.Response:
    """GET with the error taxonomy every adapter shares.

    404 -> SourceNotFound (unless `ok_404`, for existence probes); 429, 5xx, timeouts and network
    errors -> SourceTransientError (the caller retries); any other non-2xx -> SourceError.
    """
    try:
        response = await client.get(url, timeout=TIMEOUT)
    except httpx.TimeoutException as exc:
        raise SourceTransientError(f"timeout fetching {url}") from exc
    except httpx.TransportError as exc:
        raise SourceTransientError(f"network error fetching {url}: {type(exc).__name__}") from exc

    status = response.status_code
    if status == 404 and not ok_404:
        raise SourceNotFound(f"{url} returned 404")
    if status == 429 or status >= 500:
        raise SourceTransientError(f"{url} returned {status}")
    if status >= 400 and status != 404:
        raise SourceError(f"{url} returned unexpected status {status}")
    return response


def json_body(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError as exc:  # a 200 with a non-JSON body is almost always an edge/proxy blip
        raise SourceTransientError(f"{response.url} returned a non-JSON body") from exc


def parse_iso(value: object) -> datetime | None:
    """ISO-8601 string -> timezone-aware UTC datetime (None if missing or unparseable)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
