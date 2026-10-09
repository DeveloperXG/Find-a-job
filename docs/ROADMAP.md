# Roadmap

Phases, sprints and process. Per-story specs live in [`backlog/`](backlog/). Live status lives in [`../HANDOFF.md`](../HANDOFF.md).

## Context

`find-a-job` is an empty repo (README only). The goal is a personal engine that **discovers** jobs from public ATS boards, **scores** them against the user's profile (SDE / MLE / AIE), **tailors** an ATS-friendly resume, and **tracks** applications through a status pipeline. Later it will run a **daily quota workflow**: pick N curated jobs, prepare assisted applications, notify the user, and listen to Gmail for status changes (next steps, rejection, offer).

This plan breaks the work into 1-week Scrum sprints. Each story is specified tightly enough that a **Sonnet 5.5** session can execute it without guessing. It also marks the few stories where **Opus 5.5** is worth the cost.

Locked decisions, target roles and stack: see [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Model recommendation (Opus vs Sonnet)

**Sonnet 5.5 can execute about 85% of stories** because they're specified below. Use **Opus 5.5** only for:
1. **S1-02 Contracts**: domain schemas, protocols and the state machine. Every parallel track depends on these, and mistakes here are expensive to fix later.
2. **S2-02a Scoring rubric + eval set**: prompt design and judging calibration.
3. **Phase 2 email classifier + matching** (ambiguous real-world input).
4. **Phase 3 Playwright assisted-apply**: brittle, adversarial UIs and judgment calls about safety.
5. **Sprint reviews / code review** (`/code-review high` at each sprint's end) and **sprint planning** (the Scrum Master role).

Each story is tagged `[Sonnet]` or `[Opus]`.

---

## Agile operating model

- **Product Owner:** the user. Owns priorities, accepts stories at review, and makes design-direction calls.
- **Scrum Master / Tech Lead:** an Opus session at sprint planning, review and retro. It writes and refines `docs/backlog/*.md` and resolves blocked stories.
- **Dev Team:** Sonnet sessions, **one story per session, one git worktree/branch per story, one PR per story**. Parallel tracks run as concurrent sessions.
- **Cadence:** 1-week sprints. Mon: planning (30 min). Daily: every agent session ends by updating `HANDOFF.md`. Fri: review (demo against acceptance criteria) and retro (3 bullets in `docs/retros/`).
- **Dates:** Sprint 1 Oct 12–16 · Sprint 2 Oct 19–23 · Sprint 3 (stabilize + deploy) Oct 26–30, 2026.
- **Points:** Fibonacci (1, 2, 3, 5, 8). Points measure complexity and risk, not hours. Anything above 5 points is split.
- **Velocity:** start with a commitment of **~30 pts/sprint** and recalibrate after Sprint 1 using *accepted* points only. Each sprint has a **cut line**; stories below it slip without drama.

**Definition of Ready:** the story has inputs/outputs, files to touch, acceptance criteria, and dependencies merged or mocked.

**Definition of Done:** the work is merged to `main` with green CI (ruff, mypy --strict on `app/`, pytest, eslint, tsc), has tests for the acceptance criteria, has a migration if the schema changed, has regenerated TS types if the API changed, and has been demoed against real or fixture data. **AI-written code that isn't integrated and tested earns 0 points.**

---

## MVP sprints

### Sprint 1 (Oct 12–16): "Data in"
**Sprint goal:** `just ingest` pulls real jobs for the seed companies from all three ATSes into Postgres, deduplicated and deterministically filtered, and they're visible at `GET /jobs` and on a basic Feed page.
**Parallel tracks after Day 1:** A = adapters (04/05/06 at once), B = normalizers + filters (07, 10), C = web (11).

| ID | Story | Pts | Model | Depends |
|---|---|---|---|---|
| S1-01 | Repo scaffold & tooling | 3 | Sonnet | — |
| S1-02 | Domain contracts + state machine + CLAUDE.md conventions | 3 | **Opus** | 01 |
| S1-03 | ORM models + Alembic `0001_initial` | 5 | Sonnet | 02 |
| S1-04 | Greenhouse adapter | 2 | Sonnet | 02 |
| S1-05 | Lever adapter | 2 | Sonnet | 02 |
| S1-06 | Ashby adapter | 2 | Sonnet | 02 |
| S1-07 | Normalizers | 3 | Sonnet | 02 |
| S1-08 | Ingestion service + `jt ingest` CLI | 5 | Sonnet | 03–07 |
| S1-09 | Company registry, seed CSV, slug auto-detect | 3 | Sonnet | 03–06 |
| S1-10 | Preferences + deterministic filter engine | 3 | Sonnet | 03, 07 |
| — cut line — | | | | |
| S1-11 | Web scaffold + design tokens + Feed v0 | 3 | Sonnet | 01 (mock until 08) |
Total 34 (31 above the cut line).

### Sprint 2 (Oct 19–23): "Intelligence & tracking"
**Sprint goal:** new jobs are scored automatically on a schedule; the user browses a ranked feed, tailors a resume for a job, moves applications through the pipeline, and gets in-app and push notifications.

| ID | Story | Pts | Model | Depends |
|---|---|---|---|---|
| S2-01 | LLM provider + Anthropic impl + fake + cost ledger + budget guard | 3 | Sonnet | S1-03 |
| S2-02a | Scoring rubric prompt + 30-case eval set | 2 | **Opus** | S2-01 |
| S2-02b | Scoring pipeline (prescore → Haiku → cache) | 3 | Sonnet | 02a |
| S2-03 | Jobs/matches API (feed query, detail, save/dismiss) | 3 | Sonnet | S1-08 |
| S2-04 | Applications API + state machine service + notifiers (in-app, ntfy) | 3 | Sonnet | S1-02 |
| S2-05 | ResumeDoc schema, master import, Typst render | 5 | Sonnet | S2-01 |
| S2-06 | Tailoring + anti-fabrication validator + variant reuse | 5 | Sonnet | 05, 02b |
| S2-07 | Inngest workflows: discovery cron, poll fan-out, scoring batch | 3 | Sonnet | S1-08, 02b |
| S2-08 | Dashboard: Feed v1, Job detail, Pipeline board | 5 | Sonnet | 03, 04 |
| — cut line — | | | | |
| S2-09 | Daily digest workflow (in-app + push) | 2 | Sonnet | 07 |
| S2-10 | Resumes page + Settings/Preferences page + Companies page | 3 | Sonnet | 05, S1-10 |
Total 37 (32 above the cut line).

### Sprint 3 (Oct 26–30): "Stabilize & ship"
| ID | Story | Pts | Model |
|---|---|---|---|
| S3-01 | Single-user auth: argon2 hash in env, `POST /auth/login` → httpOnly SameSite=Lax signed session cookie (itsdangerous), FastAPI dependency on all routes, Next.js middleware redirect, login rate limit 5/min | 3 | Sonnet |
| S3-02 | E2E: Playwright happy path (login → feed → tailor → queue → drag to Applied → notification) + scoring eval in CI (fake provider) / nightly live | 3 | Sonnet |
| S3-03 | Railway: services `api`, `worker`, `web`, Postgres plugin; Inngest Cloud app pointed at `worker` with signing key; migrations run on deploy; daily `pg_dump` backup to S3-compatible bucket via GitHub Actions cron | 3 | Sonnet |
| S3-04 | Runs & Costs page (workflow_runs table, daily LLM spend chart, source health) | 2 | Sonnet |
| S3-05 | Carry-over from Sprint 2 cut line | ~5 | — |
| S3-06 | Bug bash, hardening, `/code-review high` sweep, README runbook | 5 | **Opus** review + Sonnet fixes |
Release criteria: 3 consecutive scheduled cycles succeed in production with no manual intervention, and daily LLM spend stays under budget.

---

## Post-MVP phases (epics; refined into stories at each planning)

**Phase 2: Gmail status listener + email channel (Sprints 4–5, ~45 pts)**
- Gmail OAuth (installed-app flow, `gmail.readonly` + `gmail.send`), refresh token encrypted at rest (Fernet key in env).
- Polling every 15 min with `history.list` from the stored `historyId` (simpler and free compared with Pub/Sub push; latency is acceptable). Pre-filter senders and subjects (ATS domains such as greenhouse-mail.io, lever.co, ashbyhq.com, plus known company domains; keywords like "application", "interview", "unfortunately").
- **[Opus]** Haiku classifier → `{category: rejection|next_steps|offer|ack|scheduling|other, company, role, confidence, stage}`. Matcher: company domain/name → candidate applications → title similarity → most recent applied.
- **Confidence gate:** ≥ 0.85 and a unique match → auto-transition (actor=email). Anything else goes to a **Review inbox** in the app ("Is this Stripe SWE → Rejected?" with one-click confirm). The system never auto-marks a rejection on low confidence.
- `EmailNotifier` via Gmail send; full rule matrix active. Auto `no_response` after 30 days (configurable).
- Cost lever: switch scheduled scoring to the **Message Batches API** (asynchronous, discounted). It fits the 6-hourly cadence.

**Phase 3: Daily quota + assisted apply (Sprints 6–8, ~60 pts)**
- **Quota planner:** each morning, pick N from the scored pool by score, then diversity (≤ 1 per company per day, respect cooldown), then freshness (posted ≤ 14 days). If fewer than N qualify, **don't silently lower the bar**: report the shortfall and offer a one-tap "relax: include ≥ 65" via the push action.
- **Answer bank:** Q&A table (question embedding-free: normalized text + canonical key like `work_auth`, `salary_expectation`, `relocation`, `why_company`). Known keys are answered deterministically; unknown questions get Sonnet drafts flagged `needs_review`; approved answers are stored for reuse.
- **[Opus]** Playwright adapters per ATS form (Greenhouse, Lever, Ashby): pre-fill fields, upload the tailored PDF, screenshot, then **pause for approval** (in-app review screen, deep-linked from push). On approval, submit and verify (confirmation page text or confirmation email). On CAPTCHA, login wall or unknown required field, hand off to the user with the form open. Bypass is never attempted.
- Quota-reached notification on all channels; applied jobs land in the Applied pool.

**Phase 4 (backlog):** analytics (funnel by role family and source, response rates), interview prep briefs, DOCX export, aggregator sources (HN Who's Hiring, RemoteOK), pgvector reuse matching (only if Jaccard reuse proves weak).

---

## Verification (MVP end-to-end)
- `just up && just migrate && just test` is green locally and in CI.
- `uv run jt companies import data/companies.seed.csv` → `uv run jt ingest --all` → second run reports 0 new (idempotency).
- `uv run jt filter --pending` → `uv run jt score --pending` → a second run makes 0 LLM calls; `jt eval scoring` ≥ 80% band accuracy.
- Inngest dev UI (localhost:8288): trigger `discovery_cron` → poll fan-out → filter_and_score all succeed; `workflow_runs` rows written.
- Web: Feed shows ranked jobs → Job detail → Tailor (the validator passes; the PDF downloads and its text extracts cleanly) → Add to queue → drag to Applied → Next Steps produces an in-app notification and an ntfy push on the phone; dragging Next Steps → Rejected also notifies; a normal Applied → Rejected produces in-app only.
- Sprint 3: the same flow on Railway behind login, with 3 consecutive scheduled cycles succeeding.
