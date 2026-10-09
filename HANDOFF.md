# HANDOFF.md — Living baton

> Every agent session **reads this first** and **updates it last**. Keep it short and current; history belongs in git.

## Now
- **Sprint:** Sprint 1 "Data in" (Mon 2026-10-12 → Fri 2026-10-16)
- **Sprint goal:** `just ingest` pulls real jobs for the seed companies from Greenhouse, Lever and Ashby into Postgres, deduplicated and deterministically filtered, and they're visible at `GET /jobs` and on a basic Feed page.
- **Last updated:** 2026-10-09 by Opus 5.5 (planning session)
- **Next action:** Product Owner reviews and merges `docs/plan` → start **S1-01** (Sonnet).

## Story board
| ID | Title | Pts | Status | Branch / PR | Owner |
|---|---|---|---|---|---|
| S1-01 | Repo scaffold & tooling | 3 | todo | | Sonnet |
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
_None._

## Blocked / decisions needed
1. **Seed company list:** PO to fill in `data/companies.seed.csv` (≥ 30 companies) before S1-09's demo. *Recommendation:* start with companies known to hire new grads/interns in AI/ML and SDE; leave the ATS token columns blank and let auto-detect fill them.
2. **Scoring eval set (S2-02a):** PO to provide 30 real postings labeled high/mid/low by Sprint 2 Monday.
3. **Master resume:** PO to provide the current resume (PDF/DOCX) for S2-05.

## Discovered work
- `README.md` was UTF-16 encoded; it's now rewritten as UTF-8 (docs/plan branch).

## Gotchas
- Windows host: use Git Bash or PowerShell; `just` must be installed (`winget install Casey.Just`). Use `host.docker.internal` for the Inngest dev server to reach the worker.

## Velocity log
| Sprint | Committed | Accepted |
|---|---|---|
| 1 | 31 (+3 below cut) | — |
