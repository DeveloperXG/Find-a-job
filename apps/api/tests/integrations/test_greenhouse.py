import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from structlog.testing import capture_logs

from app.domain.jobs import JobSource, SourceError, SourceNotFound, SourceTransientError
from app.integrations.ats.greenhouse import GreenhouseSource

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "greenhouse" / "board.json"
TOKEN = "acme"
JOBS_URL = f"https://boards-api.greenhouse.io/v1/boards/{TOKEN}/jobs"
BOARD_URL = f"https://boards-api.greenhouse.io/v1/boards/{TOKEN}"

source: JobSource = GreenhouseSource()  # the adapter satisfies the protocol (checked by mypy)


@pytest.fixture
def board() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return copy.deepcopy(data)


@respx.mock
async def test_maps_fixture_to_job_postings(board: dict[str, Any]) -> None:
    route = respx.get(JOBS_URL, params={"content": "true"}).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        postings = await source.fetch_jobs(TOKEN, client)

    assert route.called
    assert len(postings) == len(board["jobs"]) == 3
    for posting, job in zip(postings, board["jobs"], strict=True):
        assert posting.source == "greenhouse" and posting.source_token == TOKEN
        assert posting.external_id == str(job["id"])
        assert posting.title == job["title"]
        assert posting.department == job["departments"][0]["name"]
        assert posting.location_raw == job["location"]["name"]
        assert posting.locations == [job["location"]["name"]]
        assert str(posting.apply_url) == str(posting.canonical_url) == job["absolute_url"]
        assert posting.workplace_type == "onsite"  # metadata "Location Type: On-Site"
        assert posting.employment_type == "unknown"  # S1-07 infers this
        assert posting.compensation is None
        assert "content" not in posting.raw and posting.raw["id"] == job["id"]


@respx.mock
async def test_timestamps_are_utc_and_posted_at_uses_first_published(
    board: dict[str, Any],
) -> None:
    respx.get(JOBS_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        first = (await source.fetch_jobs(TOKEN, client))[0]

    assert first.posted_at == datetime(2024, 12, 20, 18, 53, 38, tzinfo=UTC)  # 13:53:38-05:00
    assert first.source_updated_at == datetime(2026, 8, 22, 1, 32, 54, tzinfo=UTC)  # 21:32:54-04:00
    assert first.posted_at is not None and first.posted_at.utcoffset() is not None


@respx.mock
async def test_description_is_unescaped_html_and_clean_text(board: dict[str, Any]) -> None:
    assert "&lt;" in board["jobs"][0]["content"]  # precondition: the API really escapes it
    respx.get(JOBS_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        first = (await source.fetch_jobs(TOKEN, client))[0]

    assert first.description_html is not None
    assert "&lt;" not in first.description_html and "<div" in first.description_html
    assert first.description_text and "<" not in first.description_text
    assert "&quot;" not in first.description_text


@respx.mock
async def test_missing_optional_fields_are_tolerated(board: dict[str, Any]) -> None:
    job = board["jobs"][0]
    for key in ("content", "location", "departments", "metadata", "first_published", "updated_at"):
        job.pop(key)
    respx.get(JOBS_URL).respond(200, json={"jobs": [job]})
    async with httpx.AsyncClient() as client:
        (posting,) = await source.fetch_jobs(TOKEN, client)

    assert posting.description_html is None and posting.description_text == ""
    assert posting.location_raw is None and posting.locations == []
    assert posting.department is None and posting.workplace_type == "unknown"
    assert posting.posted_at is None and posting.source_updated_at is None


@respx.mock
async def test_empty_board_returns_no_postings() -> None:
    respx.get(JOBS_URL).respond(200, json={"jobs": [], "meta": {"total": 0}})
    async with httpx.AsyncClient() as client:
        assert await source.fetch_jobs(TOKEN, client) == []


# --- error taxonomy -------------------------------------------------------------------------


@respx.mock
async def test_404_raises_source_not_found() -> None:
    respx.get(JOBS_URL).respond(404, json={"error": "Job not found"})
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceNotFound):
            await source.fetch_jobs(TOKEN, client)


@respx.mock
@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
async def test_429_and_5xx_raise_transient_error(status: int) -> None:
    respx.get(JOBS_URL).respond(status)
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceTransientError):
            await source.fetch_jobs(TOKEN, client)


@respx.mock
@pytest.mark.parametrize(
    "error", [httpx.ReadTimeout("slow"), httpx.ConnectTimeout("slow"), httpx.ConnectError("down")]
)
async def test_timeouts_and_network_errors_are_transient(error: httpx.HTTPError) -> None:
    respx.get(JOBS_URL).mock(side_effect=error)
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceTransientError):
            await source.fetch_jobs(TOKEN, client)


@respx.mock
async def test_other_client_errors_are_not_retried() -> None:
    respx.get(JOBS_URL).respond(403)
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceError) as info:
            await source.fetch_jobs(TOKEN, client)
    assert not isinstance(info.value, SourceTransientError | SourceNotFound)


@respx.mock
async def test_non_json_body_is_transient() -> None:
    respx.get(JOBS_URL).respond(200, text="<html>gateway hiccup</html>")
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceTransientError):
            await source.fetch_jobs(TOKEN, client)


@respx.mock
@pytest.mark.parametrize("body", [{"nope": []}, [], {"jobs": "x"}])
async def test_unexpected_shape_raises_source_error(body: object) -> None:
    respx.get(JOBS_URL).respond(200, json=body)
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceError):
            await source.fetch_jobs(TOKEN, client)


# --- a bad job never fails the batch ------------------------------------------------------


@respx.mock
async def test_malformed_job_is_skipped_and_logged(board: dict[str, Any]) -> None:
    good, no_url, no_id = board["jobs"]
    no_url = {k: v for k, v in no_url.items() if k != "absolute_url"}
    bad_url = {**no_id, "id": 999, "absolute_url": "not a url"}
    no_id = {k: v for k, v in no_id.items() if k != "id"}
    respx.get(JOBS_URL).respond(200, json={"jobs": [no_url, good, no_id, bad_url, "garbage", None]})

    with capture_logs() as logs:
        async with httpx.AsyncClient() as client:
            postings = await source.fetch_jobs(TOKEN, client)

    assert [p.external_id for p in postings] == [str(good["id"])]
    skipped = [entry for entry in logs if entry["event"] == "skipping malformed job"]
    assert len(skipped) == 5
    assert all(entry["log_level"] == "warning" for entry in skipped)
    flat = json.dumps(skipped, default=str)
    assert "About Anthropic" not in flat  # logs carry identifiers only, never posting content


# --- exists() -------------------------------------------------------------------------------


@respx.mock
async def test_exists_true_on_200() -> None:
    route = respx.get(BOARD_URL).respond(200, json={"name": "Acme"})
    async with httpx.AsyncClient() as client:
        assert await source.exists(TOKEN, client) is True
    assert route.called


@respx.mock
async def test_exists_false_on_404() -> None:
    respx.get(BOARD_URL).respond(404)
    async with httpx.AsyncClient() as client:
        assert await source.exists(TOKEN, client) is False


@respx.mock
async def test_exists_raises_transient_on_5xx() -> None:
    respx.get(BOARD_URL).respond(503)
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceTransientError):
            await source.exists(TOKEN, client)


# --- AGENTS.md section 6 ---------------------------------------------------------------------


@respx.mock
async def test_requests_use_10s_connect_30s_read_timeouts(board: dict[str, Any]) -> None:
    route = respx.get(JOBS_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:  # a bare client: the adapter must still set them
        await source.fetch_jobs(TOKEN, client)

    timeout = route.calls.last.request.extensions["timeout"]
    assert timeout["connect"] == 10.0 and timeout["read"] == 30.0
