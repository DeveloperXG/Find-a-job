"""Record a trimmed live response from a public ATS job-board API as a test fixture.

    uv run python scripts/record_fixture.py greenhouse <board-token> --record [--limit 3]

Without --record nothing is fetched or written. Only the three public job-board APIs allowed in
AGENTS.md section 6 are supported. Review the output before committing: fixtures must contain no
personal data (job boards publish none, but check anyway).
"""

import argparse
import json
from pathlib import Path
from typing import Any

import httpx

URLS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true",
    "lever": "https://api.lever.co/v0/postings/{token}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true",
}
# Where the list of jobs lives in each response (None = the response itself is the list).
JOBS_KEY = {"greenhouse": "jobs", "lever": None, "ashby": "jobs"}
FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def trim(ats: str, payload: Any, limit: int) -> Any:
    key = JOBS_KEY[ats]
    if key is None:
        return payload[:limit]
    payload[key] = payload[key][:limit]
    if "meta" in payload:
        payload["meta"] = {"total": len(payload[key])}
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ats", choices=sorted(URLS))
    parser.add_argument("token")
    parser.add_argument("--record", action="store_true", help="actually call the live API")
    parser.add_argument("--limit", type=int, default=3, help="jobs to keep")
    parser.add_argument("--name", default=None, help="fixture file name (default: <token>.json)")
    args = parser.parse_args()

    url = URLS[args.ats].format(token=args.token)
    if not args.record:
        print(f"dry run: would GET {url}")
        return

    timeout = httpx.Timeout(30.0, connect=10.0)
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url)
    response.raise_for_status()

    out = FIXTURES / args.ats / (args.name or f"{args.token}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(trim(args.ats, response.json(), args.limit), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
