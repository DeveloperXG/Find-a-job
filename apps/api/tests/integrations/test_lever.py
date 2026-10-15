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
from app.integrations.ats.lever import LeverSource

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "lever" / "board.json"
TOKEN = "acme"
US_URL = f"https://api.lever.co/v0/postings/{TOKEN}"
EU_URL = f"https://api.eu.lever.co/v0/postings/{TOKEN}"

source: JobSource = LeverSource()  # the adapter satisfies the protocol (checked by mypy)


@pytest.fixture
def board() -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return copy.deepcopy(data)


@respx.mock
async def test_maps_fixture_to_job_postings(board: list[dict[str, Any]]) -> None:
    route = respx.get(US_URL, params={"mode": "json"}).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        postings = await source.fetch_jobs(TOKEN, client)

    assert route.called
    assert len(postings) == len(board) == 3
    for posting, job in zip(postings, board, strict=True):
        assert posting.source == "lever" and posting.source_token == TOKEN
        assert posting.external_id == job["id"]
        assert posting.title == job["text"]
        assert posting.department == job["categories"]["department"]
        assert posting.location_raw == job["categories"]["location"]
        assert posting.locations == job["categories"]["allLocations"]
        assert str(posting.apply_url) == job["applyUrl"]
        assert str(posting.canonical_url) == job["hostedUrl"]
        assert posting.employment_type == "unknown"  # S1-07 infers this from `commitment`
        assert posting.raw["_region"] == "us"
        assert posting.raw["categories"]["commitment"] == "Regular Full Time (Salary)"
    assert [p.workplace_type for p in postings] == ["hybrid", "onsite", "onsite"]


@respx.mock
async def test_created_at_epoch_ms_becomes_utc_datetime(board: list[dict[str, Any]]) -> None:
    respx.get(US_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        postings = await source.fetch_jobs(TOKEN, client)

    assert postings[2].posted_at == datetime(2024, 6, 17, 14, 17, 57, 107000, tzinfo=UTC)
    assert postings[0].posted_at == datetime.fromtimestamp(1788199939.703, tz=UTC)
    assert all(p.posted_at is not None and p.posted_at.utcoffset() is not None for p in postings)
    assert all(p.source_updated_at is None for p in postings)  # Lever exposes no updated time


@respx.mock
async def test_salary_range_maps_to_compensation(board: list[dict[str, Any]]) -> None:
    board[1]["salaryRange"]["interval"] = "per-hour-wage"
    board[2]["salaryRange"] = {
        "min": 5,
        "max": 6,
        "currency": "GBP",
        "interval": "per-month-salary",
    }
    respx.get(US_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        first, hourly, monthly = await source.fetch_jobs(TOKEN, client)

    assert first.compensation is not None
    assert (first.compensation.min, first.compensation.max) == (85000, 175000)
    assert first.compensation.currency == "USD" and first.compensation.interval == "year"
    assert hourly.compensation is not None and hourly.compensation.interval == "hour"
    assert monthly.compensation is not None and monthly.compensation.interval == "unknown"


@respx.mock
async def test_no_salary_range_means_no_compensation(board: list[dict[str, Any]]) -> None:
    assert "salaryRange" not in board[2]  # precondition: the third recorded job has none
    respx.get(US_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        postings = await source.fetch_jobs(TOKEN, client)

    assert postings[2].compensation is None


@respx.mock
async def test_description_concatenates_body_lists_and_additional(
    board: list[dict[str, Any]],
) -> None:
    job = board[0]
    job["additional"] = "<div>Equal opportunity employer.</div>"
    job["additionalPlain"] = "Equal opportunity employer."
    respx.get(US_URL).respond(200, json=[job])
    async with httpx.AsyncClient() as client:
        (posting,) = await source.fetch_jobs(TOKEN, client)

    text = posting.description_text
    heading = job["lists"][0]["text"]
    assert text.startswith(job["descriptionPlain"].strip()[:40])
    assert text.index(heading) < text.index("Equal opportunity employer.")
    assert "<li>" not in text and "<div" not in text  # list HTML is converted to text
    assert posting.description_html is not None
    assert f"<h3>{heading}</h3><ul>" in posting.description_html
    assert posting.description_html.endswith("<div>Equal opportunity employer.</div>")


@respx.mock
async def test_body_fields_are_not_duplicated_into_raw(board: list[dict[str, Any]]) -> None:
    respx.get(US_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        postings = await source.fetch_jobs(TOKEN, client)

    for posting in postings:
        assert {"description", "descriptionPlain", "lists", "additional"}.isdisjoint(posting.raw)
        assert posting.raw["id"] == posting.external_id


@respx.mock
async def test_missing_optional_fields_are_tolerated(board: list[dict[str, Any]]) -> None:
    job = {k: board[0][k] for k in ("id", "text", "hostedUrl", "applyUrl")}
    respx.get(US_URL).respond(200, json=[job])
    async with httpx.AsyncClient() as client:
        (posting,) = await source.fetch_jobs(TOKEN, client)

    assert posting.description_html is None and posting.description_text == ""
    assert posting.location_raw is None and posting.locations == []
    assert posting.department is None and posting.workplace_type == "unknown"
    assert posting.compensation is None and posting.posted_at is None


@respx.mock
async def test_single_location_falls_back_and_team_replaces_department(
    board: list[dict[str, Any]],
) -> None:
    job = board[0]
    job["categories"] = {"location": "Remote - US", "team": "Platform"}
    respx.get(US_URL).respond(200, json=[job])
    async with httpx.AsyncClient() as client:
        (posting,) = await source.fetch_jobs(TOKEN, client)

    assert posting.locations == ["Remote - US"] and posting.department == "Platform"


@respx.mock
async def test_empty_board_returns_no_postings() -> None:
    respx.get(US_URL).respond(200, json=[])
    async with httpx.AsyncClient() as client:
        assert await source.fetch_jobs(TOKEN, client) == []


# --- region fallback ------------------------------------------------------------------------


@respx.mock
async def test_us_404_falls_back_to_eu_and_records_region(board: list[dict[str, Any]]) -> None:
    us = respx.get(US_URL).respond(404, json={"ok": False, "error": "Document not found"})
    eu = respx.get(EU_URL, params={"mode": "json"}).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        postings = await source.fetch_jobs(TOKEN, client)

    assert us.called and eu.called
    assert len(postings) == 3 and {p.raw["_region"] for p in postings} == {"eu"}


@respx.mock
async def test_eu_is_not_tried_when_us_succeeds(board: list[dict[str, Any]]) -> None:
    respx.get(US_URL).respond(200, json=board)
    eu = respx.get(EU_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:
        await source.fetch_jobs(TOKEN, client)

    assert not eu.called


@respx.mock
async def test_404_in_both_regions_raises_source_not_found() -> None:
    respx.get(US_URL).respond(404)
    respx.get(EU_URL).respond(404)
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceNotFound):
            await source.fetch_jobs(TOKEN, client)


@respx.mock
async def test_us_5xx_does_not_fall_back_to_eu() -> None:
    respx.get(US_URL).respond(503)
    eu = respx.get(EU_URL).respond(200, json=[])
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceTransientError):
            await source.fetch_jobs(TOKEN, client)

    assert not eu.called


@respx.mock
async def test_eu_5xx_after_us_404_is_transient() -> None:
    respx.get(US_URL).respond(404)
    respx.get(EU_URL).respond(502)
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceTransientError):
            await source.fetch_jobs(TOKEN, client)


# --- error taxonomy -------------------------------------------------------------------------


@respx.mock
@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
async def test_429_and_5xx_raise_transient_error(status: int) -> None:
    respx.get(US_URL).respond(status)
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceTransientError):
            await source.fetch_jobs(TOKEN, client)


@respx.mock
@pytest.mark.parametrize(
    "error", [httpx.ReadTimeout("slow"), httpx.ConnectTimeout("slow"), httpx.ConnectError("down")]
)
async def test_timeouts_and_network_errors_are_transient(error: httpx.HTTPError) -> None:
    respx.get(US_URL).mock(side_effect=error)
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceTransientError):
            await source.fetch_jobs(TOKEN, client)


@respx.mock
async def test_other_client_errors_are_not_retried() -> None:
    respx.get(US_URL).respond(403)
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceError) as info:
            await source.fetch_jobs(TOKEN, client)
    assert not isinstance(info.value, SourceTransientError | SourceNotFound)


@respx.mock
async def test_non_json_body_is_transient() -> None:
    respx.get(US_URL).respond(200, text="<html>gateway hiccup</html>")
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceTransientError):
            await source.fetch_jobs(TOKEN, client)


@respx.mock
@pytest.mark.parametrize("body", [{"nope": []}, "x", None])
async def test_unexpected_shape_raises_source_error(body: object) -> None:
    respx.get(US_URL).respond(200, json=body)
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceError):
            await source.fetch_jobs(TOKEN, client)


# --- a bad job never fails the batch ------------------------------------------------------


@respx.mock
async def test_malformed_job_is_skipped_and_logged(board: list[dict[str, Any]]) -> None:
    good, no_url, no_id = board
    no_url = {k: v for k, v in no_url.items() if k != "hostedUrl"}
    bad_url = {**no_id, "id": "bad-url", "applyUrl": "not a url"}
    no_title = {k: v for k, v in no_id.items() if k != "text"}
    no_id = {k: v for k, v in no_id.items() if k != "id"}
    respx.get(US_URL).respond(200, json=[no_url, good, no_id, bad_url, no_title, "garbage", None])

    with capture_logs() as logs:
        async with httpx.AsyncClient() as client:
            postings = await source.fetch_jobs(TOKEN, client)

    assert [p.external_id for p in postings] == [good["id"]]
    skipped = [entry for entry in logs if entry["event"] == "skipping malformed job"]
    assert len(skipped) == 6
    assert all(entry["log_level"] == "warning" for entry in skipped)
    flat = json.dumps(skipped, default=str)
    assert "Skill Set" not in flat and good["text"] not in flat  # identifiers only, no content


# --- exists() -------------------------------------------------------------------------------


@respx.mock
async def test_exists_true_on_us_200() -> None:
    route = respx.get(US_URL).respond(200, json=[])
    async with httpx.AsyncClient() as client:
        assert await source.exists(TOKEN, client) is True
    assert route.called


@respx.mock
async def test_exists_checks_eu_when_us_404s() -> None:
    respx.get(US_URL).respond(404)
    eu = respx.get(EU_URL).respond(200, json=[])
    async with httpx.AsyncClient() as client:
        assert await source.exists(TOKEN, client) is True
    assert eu.called


@respx.mock
async def test_exists_false_when_both_regions_404() -> None:
    respx.get(US_URL).respond(404)
    respx.get(EU_URL).respond(404)
    async with httpx.AsyncClient() as client:
        assert await source.exists(TOKEN, client) is False


@respx.mock
async def test_exists_raises_transient_on_5xx() -> None:
    respx.get(US_URL).respond(503)
    async with httpx.AsyncClient() as client:
        with pytest.raises(SourceTransientError):
            await source.exists(TOKEN, client)


# --- AGENTS.md section 6 ---------------------------------------------------------------------


@respx.mock
async def test_requests_use_10s_connect_30s_read_timeouts(board: list[dict[str, Any]]) -> None:
    route = respx.get(US_URL).respond(200, json=board)
    async with httpx.AsyncClient() as client:  # a bare client: the adapter must still set them
        await source.fetch_jobs(TOKEN, client)

    timeout = route.calls.last.request.extensions["timeout"]
    assert timeout["connect"] == 10.0 and timeout["read"] == 30.0
