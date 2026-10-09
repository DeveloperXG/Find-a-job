# HANDOFF.md — Living baton

> Every agent session **reads this first** and **updates it last**. Keep it short and current; history belongs in git.

## Now
- **Sprint:** Sprint 1 "Data in" (Mon 2026-10-12 → Fri 2026-10-16)
- **Sprint goal:** `just ingest` pulls real jobs for the seed companies from Greenhouse, Lever and Ashby into Postgres, deduplicated and deterministically filtered, and they're visible at `GET /jobs` and on a basic Feed page.
- **Last updated:** 2026-10-09 by Sonnet 5.5 (S1-01 session)
- **Next action:** PO reviews/merges the S1-01 PR (stacked on `docs/plan`) -> run **S1-02 (Opus only)**. Sonnet must not start S1-03..S1-07 until S1-02 is merged.

## Story board
| ID | Title | Pts | Status | Branch / PR | Owner |
|---|---|---|---|---|---|
| S1-01 | Repo scaffold & tooling | 3 | review | story/S1-01-repo-scaffold (PR open) | Sonnet |
| S1-02 | Domain contracts + state machine | 3 | todo | | **Opus** |
| S1-03 | ORM models + Alembic 0001 | 5 | todo | | Sonnet |
| S1-04 | Greenhouse adapter | 2 | todo | | Sonnet |
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
- **S1-01** is in review. Done: uv API project (stubs: main/worker/config/db/cli + /health smoke test), Next 15 + shadcn web app, compose, justfile, .env.example, CI.
  - Verified locally: `just migrate` / `just test` / `just lint` on PowerShell and Git Bash (`just test-api` on Git Bash); `jt` CLI boots.
  - **Not verified:** `just up` (Docker is not installed on this machine) and the CI workflow (runs on the PR). PO or reviewer should run `just up` once.
  - Next step: merge, then S1-02 (Opus).

## Blocked / decisions needed
1. **Seed company list:** PO to fill in `data/companies.seed.csv` (≥ 30 companies) before S1-09's demo. *Recommendation:* start with companies known to hire new grads/interns in AI/ML and SDE; leave the ATS token columns blank and let auto-detect fill them.
2. **Scoring eval set (S2-02a):** PO to provide 30 real postings labeled high/mid/low by Sprint 2 Monday.
3. **Master resume:** PO to provide the current resume (PDF/DOCX) for S2-05.

## Discovered work
- `README.md` was UTF-16 encoded; it's now rewritten as UTF-8 (docs/plan branch).
- Nested `apps/web/AGENTS.md` is not generated on Next 15, but Next 16 (create-next-app@latest) generates one; keep Next on 15 per ARCHITECTURE.md.

## Gotchas
- Windows host: use Git Bash or PowerShell; `just` must be installed (`winget install Casey.Just`). Use `host.docker.internal` for the Inngest dev server to reach the worker.
- `uv`/`pnpm` installed via `pip install --user uv` and `npm i -g pnpm`; `just` via winget. Open a new shell (or refresh PATH) after installing; `uv` lives in `%APPDATA%\Python\Python313\Scripts`.
- PowerShell 5.1 `Set-Content -Encoding utf8` writes a BOM, which breaks `.python-version` and TOML; write files without BOM.
- pnpm 12 uses `allowBuilds` in `pnpm-workspace.yaml` (not `onlyBuiltDependencies`).
- `just migrate` is a no-op until S1-03 adds `alembic.ini`; `just gen-types` is a stub until S1-11. `just test-web` is a production build until Playwright lands (S3-02).
- `just lint` uses `uv --directory` one command per line so a failure in an early command cannot be masked in PowerShell.

## Velocity log
| Sprint | Committed | Accepted |
|---|---|---|
| 1 | 31 (+3 below cut) | — |
