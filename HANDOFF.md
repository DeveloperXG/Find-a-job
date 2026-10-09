# HANDOFF.md — Living baton

> Every agent session **reads this first** and **updates it last**. Keep it short and current; history belongs in git.

## Now
- **Sprint:** Sprint 1 "Data in" (Mon 2026-10-12 → Fri 2026-10-16)
- **Sprint goal:** `just ingest` pulls real jobs for the seed companies from Greenhouse, Lever and Ashby into Postgres, deduplicated and deterministically filtered, and they're visible at `GET /jobs` and on a basic Feed page.
- **Last updated:** 2026-10-09 by Sonnet 5.5 (S1-04 session)
- **Next action:** PO reviews/merges the S1-04 PR (#6). S1-03 is merged, so S1-08/09/10 are unblocked. Remaining parallel Sonnet stories: S1-05, S1-06, S1-07, S1-11 (branch each from `main`).

## Story board
| ID | Title | Pts | Status | Branch / PR | Owner |
|---|---|---|---|---|---|
| S1-01 | Repo scaffold & tooling | 3 | done | PR #2 (merged) | Sonnet |
| S1-02 | Domain contracts + state machine | 3 | done | PR #4 (merged) | **Opus** |
| S1-03 | ORM models + Alembic 0001 | 5 | done | PR #5 (merged) | Sonnet |
| S1-04 | Greenhouse adapter | 2 | review | story/S1-04-greenhouse-adapter (PR #6) | Sonnet |
| S1-05 | Lever adapter | 2 | todo | | Sonnet |
| S1-06 | Ashby adapter | 2 | todo | | Sonnet |
| S1-07 | Normalizers | 3 | todo | | Sonnet |
| S1-08 | Ingestion service + `jt ingest` | 5 | todo | | Sonnet |
| S1-09 | Company registry + slug detect | 3 | todo | | Sonnet |
| S1-10 | Preferences + filter engine | 3 | todo | | Sonnet |
| — cut line — | | | | | |
| S1-11 | Web scaffold + Feed v0 | 3 | todo | | Sonnet |

Execution order: S1-01 → S1-02 → in parallel {S1-03, S1-04, S1-05, S1-06, S1-07, S1-11} → in parallel {S1-08, S1-09, S1-10}.

## In flight
- **S1-04** is in review. Done: `integrations/ats/{base,greenhouse}.py`, `scripts/record_fixture.py` (shared by S1-05/06), fixture `tests/fixtures/greenhouse/board.json`, 24 tests.
  - Verified: ruff, `mypy --strict`, pytest (no DB needed). **Not verified:** CI (first run is the PR).
  - Reuse for S1-05/06: `ats/base.py` has `get()` (the 404 / 429+5xx / other error mapping, per-request 10s/30s timeouts), `json_body()` and `parse_iso()`. Record fixtures with `uv run python scripts/record_fixture.py <ats> <token> --record`.

## Blocked / decisions needed
1. **Seed company list:** PO to fill in `data/companies.seed.csv` (≥ 30 companies) before S1-09's demo. *Recommendation:* start with companies known to hire new grads/interns in AI/ML and SDE; leave the ATS token columns blank and let auto-detect fill them.
2. **Scoring eval set (S2-02a):** PO to provide 30 real postings labeled high/mid/low by Sprint 2 Monday.
3. **Master resume:** PO to provide the current resume (PDF/DOCX) for S2-05.

## Discovered work
- `README.md` is **still UTF-16** in the repo (the earlier note saying it was converted was wrong; `file README.md` reports `data`). GitHub renders it, but greps and diffs fail. Candidate chore: re-save it as UTF-8 without BOM.
- Nested `apps/web/AGENTS.md` is not generated on Next 15, but Next 16 (create-next-app@latest) generates one; keep Next on 15 per ARCHITECTURE.md.

## Gotchas
- Windows host: use Git Bash or PowerShell; `just` must be installed (`winget install Casey.Just`). Use `host.docker.internal` for the Inngest dev server to reach the worker.
- `uv`/`pnpm` installed via `pip install --user uv` and `npm i -g pnpm`; `just` via winget. Open a new shell (or refresh PATH) after installing; `uv` lives in `%APPDATA%\Python\Python313\Scripts`.
- PowerShell 5.1 `Set-Content -Encoding utf8` writes a BOM, which breaks `.python-version` and TOML; write files without BOM.
- pnpm 12 uses `allowBuilds` in `pnpm-workspace.yaml` (not `onlyBuiltDependencies`).
- `just gen-types` is a stub until S1-11 (`just migrate` is real since S1-03). `just test-web` is a production build until Playwright lands (S3-02).
- Contracts are frozen after S1-02 merges (AGENTS.md §2). If a Sonnet story needs a new field or enum value, record it under Blocked / decisions needed instead of editing `app/domain/**`.
- `just lint` uses `uv --directory` one command per line so a failure in an early command cannot be masked in PowerShell.
- **No Docker on the dev machine.** To run the DB tests locally without it, start an embedded Postgres (does not touch the project deps): `uv run --python 3.12 --with pgserver python -c "import pgserver; print(pgserver.get_server(r'<dir>', cleanup_mode=None).get_uri())"`, create databases `jt` and `jt_test` (e.g. via asyncpg as user `postgres`, no password), then export `DATABASE_URL` and `TEST_DATABASE_URL` as `postgresql+asyncpg://postgres@127.0.0.1:<port>/<db>`. The `C:\Program Files\PostgreSQL8` folder is a broken remnant (no server binaries), don't rely on it.
- `sa.Enum(native_enum=False)` creates `VARCHAR(len(longest value))`. Widening an enum later needs a migration that alters the column type, not just the CHECK.
- Alembic autogenerate emits each enum CHECK twice (type + table). `0001` was hand-edited to keep one (named `ck_<table>_<enum>`) with `create_constraint=False` on the column types. Expect the same cleanup in future autogenerated migrations that add enum columns.
- Async SQLAlchemy: `Base` sets `eager_defaults=True` so server defaults (id, timestamps) are populated on INSERT; never access an expired attribute outside `await session.refresh(...)`.
- Greenhouse's API *does* have a publish date (`first_published`); the story notes said it did not. The adapter maps it to `posted_at` and keeps `updated_at` as `source_updated_at`. Expect similar drift in the Lever/Ashby notes: trust the recorded fixture.
- Adapters catch `Exception` per job (AGENTS 9a), so a non-dict entry in the jobs array is skipped too.

## Velocity log
| Sprint | Committed | Accepted |
|---|---|---|
| 1 | 31 (+3 below cut) | — |
