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
from app.integrations.ats.ashby import AshbySource

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ashby" / "board.json"
TOKEN = "acme"
JOBS_URL = f"https://api.ashbyhq.com/posting-api/job-board/{TOKEN}"

source: JobSource = AshbySource()  # the adapter satisfies the protocol (checked by mypy)


@pytest.fixture
def board() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return copy.deepcopy(data)


@respx.mock
async def test_maps_fixture_to_job_postings(board: dict[str, Any]) -> None:
    route = respx.get(JOBS_URL, params={"includeCompensation": "true"}).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        postings = await source.fetch_jobs(TOKEN, client)

    assert route.called
    assert len(postings) == len(board["jobs"]) == 4
    for posting, job in zip(postings, board["jobs"], strict=True):
        assert posting.source == "ashby" and posting.source_token == TOKEN
        assert posting.external_id == job["id"]
        assert posting.title == job["title"].strip()
        assert posting.department == job["department"]
        assert posting.location_raw == job["location"]
        assert posting.locations[0] == job["location"]
        assert str(posting.apply_url) == job["applyUrl"]
        assert str(posting.canonical_url) == job["jobUrl"]
        assert posting.workplace_type == "hybrid"
        assert posting.employment_type == "full_time"
        assert posting.description_html == job["descriptionHtml"]
        assert posting.description_text == job["descriptionPlain"]
        assert "descriptionHtml" not in posting.raw and posting.raw["id"] == job["id"]


@respx.mock
async def test_title_whitespace_is_stripped(board: dict[str, Any]) -> None:
    assert board["jobs"][0]["title"].startswith(" ")  # precondition: the API really sends it
    respx.get(JOBS_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        first = (await source.fetch_jobs(TOKEN, client))[0]
    assert first.title == "Security Engineer, Cloud"


@respx.mock
async def test_locations_include_secondary_without_duplicates(board: dict[str, Any]) -> None:
    job = board["jobs"][0]
    job["secondaryLocations"].append({"location": job["location"]})  # duplicate of the primary
    respx.get(JOBS_URL).respond(200, json={"jobs": [job]})
    async with httpx.AsyncClient() as client:
        (posting,) = await source.fetch_jobs(TOKEN, client)

    assert posting.locations == [
        "New York, NY (HQ)",
        "Remote (Canada)",
        "Remote (US)",
        "Miami, FL",
    ]


@respx.mock
async def test_posted_at_is_utc(board: dict[str, Any]) -> None:
    respx.get(JOBS_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        first = (await source.fetch_jobs(TOKEN, client))[0]

    assert first.posted_at == datetime(2026, 4, 7, 17, 12, 35, 753000, tzinfo=UTC)
    assert first.source_updated_at is None  # Ashby exposes no updated timestamp


@respx.mock
async def test_unlisted_jobs_are_skipped(board: dict[str, Any]) -> None:
    board["jobs"][1]["isListed"] = False
    respx.get(JOBS_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        postings = await source.fetch_jobs(TOKEN, client)

    assert [p.external_id for p in postings] == [
        job["id"] for i, job in enumerate(board["jobs"]) if i != 1
    ]


# --- compensation ---------------------------------------------------------------------------


@respx.mock
async def test_salary_component_maps_to_compensation(board: dict[str, Any]) -> None:
    respx.get(JOBS_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        postings = await source.fetch_jobs(TOKEN, client)

    first = postings[0].compensation
    assert first is not None
    assert (first.min, first.max, first.currency, first.interval) == (
        211400,
        290600,
        "USD",
        "year",
    )
    # Equity is listed before salary on some jobs and after on others: salary is still found.
    assert all(p.compensation is not None and p.compensation.currency == "USD" for p in postings)


@respx.mock
async def test_hourly_salary_and_tier_fallback(board: dict[str, Any]) -> None:
    job = board["jobs"][0]
    salary = {
        "compensationType": "Salary",
        "interval": "1 HOUR",
        "currencyCode": "USD",
        "minValue": 40,
        "maxValue": 60,
    }
    job["compensation"] = {"compensationTiers": [{"components": [salary]}]}  # no summaryComponents
    respx.get(JOBS_URL).respond(200, json={"jobs": [job]})
    async with httpx.AsyncClient() as client:
        (posting,) = await source.fetch_jobs(TOKEN, client)

    assert posting.compensation is not None
    assert (posting.compensation.min, posting.compensation.max) == (40, 60)
    assert posting.compensation.interval == "hour"


@respx.mock
async def test_equity_only_or_missing_compensation_is_none(board: dict[str, Any]) -> None:
    equity = {"compensationType": "EquityPercentage", "interval": "NONE", "minValue": None}
    board["jobs"][0]["compensation"] = {"summaryComponents": [equity]}
    del board["jobs"][1]["compensation"]
    board["jobs"][2]["compensation"] = None
    respx.get(JOBS_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        postings = await source.fetch_jobs(TOKEN, client)

    assert [p.compensation for p in postings[:3]] == [None, None, None]
    assert postings[3].compensation is not None


# --- optional fields and enum mapping ---------------------------------------------------------


@respx.mock
async def test_missing_optional_fields_are_tolerated(board: dict[str, Any]) -> None:
    job = board["jobs"][0]
    for key in (
        "descriptionHtml",
        "descriptionPlain",
        "location",
        "secondaryLocations",
        "department",
        "workplaceType",
        "employmentType",
        "publishedAt",
        "compensation",
    ):
        job.pop(key)
    respx.get(JOBS_URL).respond(200, json={"jobs": [job]})
    async with httpx.AsyncClient() as client:
        (posting,) = await source.fetch_jobs(TOKEN, client)

    assert posting.description_html is None and posting.description_text == ""
    assert posting.location_raw is None and posting.locations == []
    assert posting.department is None and posting.compensation is None
    assert posting.workplace_type == "unknown" and posting.employment_type == "unknown"
    assert posting.posted_at is None


@respx.mock
async def test_text_falls_back_to_html_when_plain_is_missing(board: dict[str, Any]) -> None:
    board["jobs"][0].pop("descriptionPlain")
    respx.get(JOBS_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        first = (await source.fetch_jobs(TOKEN, client))[0]

    assert first.description_text and "<" not in first.description_text


@respx.mock
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("FullTime", "full_time"),
        ("PartTime", "part_time"),
        ("Intern", "internship"),
        ("Contract", "contract"),
        ("Temporary", "contract"),
        ("Something", "unknown"),
    ],
)
async def test_employment_type_mapping(board: dict[str, Any], raw: str, expected: str) -> None:
    board["jobs"][0]["employmentType"] = raw
    respx.get(JOBS_URL).respond(200, json={"jobs": [board["jobs"][0]]})
    async with httpx.AsyncClient() as client:
        (posting,) = await source.fetch_jobs(TOKEN, client)
    assert posting.employment_type == expected


@respx.mock
@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Remote", "remote"), ("Hybrid", "hybrid"), ("OnSite", "onsite"), ("Weird", "unknown")],
)
async def test_workplace_type_mapping(board: dict[str, Any], raw: str, expected: str) -> None:
    board["jobs"][0]["workplaceType"] = raw
    respx.get(JOBS_URL).respond(200, json={"jobs": [board["jobs"][0]]})
    async with httpx.AsyncClient() as client:
        (posting,) = await source.fetch_jobs(TOKEN, client)
    assert posting.workplace_type == expected


@respx.mock
async def test_empty_board_returns_no_postings() -> None:
    respx.get(JOBS_URL).respond(200, json={"jobs": [], "apiVersion": "1"})
    async with httpx.AsyncClient() as client:
        assert await source.fetch_jobs(TOKEN, client) == []


# --- error taxonomy -------------------------------------------------------------------------


@respx.mock
async def test_404_raises_source_not_found() -> None:
    respx.get(JOBS_URL).respond(404, json={"error": "not found"})
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
    good, no_url, no_id, _ = board["jobs"]
    no_url = {k: v for k, v in no_url.items() if k != "jobUrl"}
    bad_url = {**no_id, "id": "bad-url", "applyUrl": "not a url"}
    no_id = {k: v for k, v in no_id.items() if k != "id"}
    respx.get(JOBS_URL).respond(200, json={"jobs": [no_url, good, no_id, bad_url, "garbage", None]})

    with capture_logs() as logs:
        async with httpx.AsyncClient() as client:
            postings = await source.fetch_jobs(TOKEN, client)

    assert [p.external_id for p in postings] == [good["id"]]
    skipped = [entry for entry in logs if entry["event"] == "skipping malformed job"]
    assert len(skipped) == 5
    assert all(entry["log_level"] == "warning" for entry in skipped)
    flat = json.dumps(skipped, default=str)
    assert good["descriptionPlain"][:40] not in flat  # identifiers only, never posting content


# --- exists() -------------------------------------------------------------------------------


@respx.mock
async def test_exists_true_on_200() -> None:
    route = respx.get(JOBS_URL).respond(200, json={"jobs": []})
    async with httpx.AsyncClient() as client:
        assert await source.exists(TOKEN, client) is True
    assert route.called


@respx.mock
async def test_exists_false_on_404() -> None:
    respx.get(JOBS_URL).respond(404)
    async with httpx.AsyncClient() as client:
        assert await source.exists(TOKEN, client) is False


@respx.mock
async def test_exists_raises_transient_on_5xx() -> None:
    respx.get(JOBS_URL).respond(503)
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
