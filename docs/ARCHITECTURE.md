# Architecture & Design Reference

Source of truth for contracts, schema, state machine and cross-cutting decisions. Changing anything under *Core contracts*, *Database schema* or the state machine requires an **[Opus]** story (see AGENTS.md §2).

## Locked decisions (from Q&A)
| Topic | Decision |
|---|---|
| LLM | **Provider-agnostic** `LLMProvider` interface. Initial models: `claude-haiku-5-5` (scoring, extraction, email classification) and `claude-sonnet-5-5` (resume tailoring, screening answers) |
| Apply mode (future) | **Assisted + approval**: system tailors, drafts and pre-fills; the user approves; it stops at any CAPTCHA |
| Phone alerts | **Push app (ntfy)**. No SMS/Twilio |
| Email | **Gmail** (API; read-only scope for the listener, send scope for digests) |
| Companies | **Seed list + auto-discover**: user CSV plus slug auto-detection across the three ATSes |
| Hosting | **Local first** (docker-compose Postgres), Railway in Sprint 3 |
| Capacity | 20 h/week of user time, AI-augmented. **MVP in 2 weeks, week 3 for stabilization** |
| MVP scope | Discovery, AI matching, resume tailoring, application tracking, scheduled workflows. **Deferred:** autonomous submission and advanced email classification |

## Target roles (Product Owner list; drives filters, prescore and scoring)
Level band: **intern, new grad, junior/entry (L1/SDE I), fellowship/residency**. Mid level and above is filtered out deterministically.
| Role family | Titles in scope (seed for `infer_role_family` + prescore title terms) |
|---|---|
| `sde` | Junior Software Engineer (SDE I), New Grad Software Engineer, Software Engineering Intern, Backend Software Engineer (Junior), Python Developer (Junior), Full-Stack Developer (Junior) |
| `mle` | Machine Learning Engineer (Junior), Machine Learning Intern, Applied Scientist Intern |
| `aie` | AI Engineer, Applied AI Engineer, AI Evaluation Engineer (Junior), AI Safety Engineer (Junior) |
| `research` | AI Research Engineer (Entry-Level), AI/ML Research Intern, AI Research Fellow, AI/ML Resident |
| `data_science` | Data Scientist (Junior) |
| `robotics` | Robotics Software Engineer (Junior) |
| `cv` | Computer Vision Engineer (Junior) |
Notes: "AI Engineer" and "Applied AI Engineer" often carry no level in the title. They pass the seniority filter as `unknown` and the LLM's experience subscore decides, with a hard reject only when the text says "5+ years" or more (regex `(\d+)\+?\s*years` with a value ≥ 4 → `yoe_too_high`). Fellowships and residencies get `employment_type="fellowship"` and are treated as entry level.

## Stack (unchanged from the user's doc, with three additions)
Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) + Alembic + PostgreSQL 16 · Next.js 15 (App Router) + TypeScript + Tailwind + shadcn/ui + TanStack Query · Inngest Python SDK · httpx · Pydantic v2 · pytest + respx · `uv` / `pnpm`. The three additions:
- **Typst** (`typst` PyPI package) for resume PDFs. It produces text-based, ATS-parseable PDFs, ships as a pure wheel, and avoids WeasyPrint's GTK dependency on Windows.
- **openapi-typescript + openapi-fetch** to generate TS types and a client from FastAPI's `/openapi.json`.
- **Typer** CLI (`jt`) so every workflow can run without Inngest, for debugging and for Sonnet's tests.

---

## Architecture

```
apps/web (Next.js) ──HTTP──▶ apps/api  FastAPI "web" process  (uvicorn app.main:app)
                                  │
                                  ├── same codebase, second process: "worker"
                                  │   (uvicorn app.worker:app — serves /api/inngest only)
                                  ▼
                         PostgreSQL (system of record)
Inngest (dev server locally / Inngest Cloud in prod) ──invokes──▶ worker /api/inngest
External: Greenhouse/Lever/Ashby public APIs · Anthropic API · ntfy · Gmail (Phase 2)
```
Inngest calls functions over HTTP. The "worker" is therefore a second FastAPI app that mounts only the Inngest handler, so long-running ingestion and scoring never compete with dashboard requests.

### Repository layout
```
find-a-job/
├── AGENTS.md                     # FIRM rules for any agent (Claude Code, Codex): constraints, forbidden actions, conventions
├── CLAUDE.md                     # one line: `@AGENTS.md` (+ Claude-specific notes) so both tools share one rulebook
├── HANDOFF.md                    # living baton: current sprint, in-flight stories, next action, gotchas (replaces STATUS.md)
├── docs/ ROADMAP.md  ARCHITECTURE.md  backlog/S1-01.md …  retros/
├── apps/
│   ├── api/
│   │   ├── pyproject.toml        # uv-managed
│   │   ├── app/
│   │   │   ├── main.py  worker.py  config.py  db.py  cli.py
│   │   │   ├── domain/           # pydantic schemas, enums, protocols, state machine (NO I/O)
│   │   │   ├── models/           # SQLAlchemy ORM
│   │   │   ├── api/              # routers: jobs.py applications.py resumes.py preferences.py companies.py runs.py
│   │   │   ├── integrations/ats/ greenhouse.py lever.py ashby.py base.py detect.py
│   │   │   ├── integrations/llm/ base.py anthropic.py fake.py
│   │   │   ├── integrations/notify/ base.py inapp.py ntfy.py
│   │   │   ├── ingestion/        normalize.py service.py
│   │   │   ├── matching/         filters.py prescore.py scorer.py prompts/
│   │   │   ├── resumes/          schema.py render.py tailor.py validate.py reuse.py templates/resume.typ
│   │   │   ├── applications/     service.py
│   │   │   └── workflows/        discovery.py scoring.py digest.py
│   │   ├── migrations/
│   │   └── tests/  fixtures/{greenhouse,lever,ashby}/*.json  evals/scoring_cases.jsonl
│   └── web/                      # Next.js
├── packages/contracts/           # generated: openapi.json + schema.d.ts
├── infra/docker-compose.yml      # postgres:16 + inngest dev server
├── data/companies.seed.csv
└── justfile                      # dev, test, lint, gen-types, migrate, ingest
```

---

## Core contracts (S1-02 produces these; everything else codes against them)

```python
# domain/enums.py
ATS = Literal["greenhouse","lever","ashby"]
WorkplaceType = Literal["remote","hybrid","onsite","unknown"]
EmploymentType = Literal["full_time","part_time","contract","internship","fellowship","unknown"]
Seniority = Literal["intern","new_grad","junior","mid","senior","staff_plus","manager","unknown"]
RoleFamily = Literal["sde","mle","aie","research","data_science","robotics","cv","data_eng","other"]
AppStatus = Literal["queued","applied","next_steps","no_response","offer",
                    "rejected","withdrawn","accepted","declined","archived"]

# domain/jobs.py
class Compensation(BaseModel): min: float|None; max: float|None; currency: str|None; interval: Literal["year","hour","unknown"]
class JobPosting(BaseModel):           # what every adapter returns
    source: ATS; source_token: str; external_id: str
    title: str; department: str|None
    description_html: str|None; description_text: str
    location_raw: str|None; locations: list[str]
    workplace_type: WorkplaceType; employment_type: EmploymentType
    compensation: Compensation|None
    apply_url: HttpUrl; canonical_url: HttpUrl
    posted_at: datetime|None; source_updated_at: datetime|None
    raw: dict[str, Any]

class SourceError(Exception): ...           # base
class SourceNotFound(SourceError): ...      # 404, not retried
class SourceTransientError(SourceError): ...# 429/5xx/timeout/network, caller retries

class JobSource(Protocol):
    ats: ATS
    async def fetch_jobs(self, token: str, client: httpx.AsyncClient) -> list[JobPosting]: ...
    async def exists(self, token: str, client: httpx.AsyncClient) -> bool: ...

# integrations/llm/base.py
class LLMTask(StrEnum): SCORE="score"; EXTRACT="extract"; TAILOR="tailor"; CLASSIFY_EMAIL="classify_email"; ANSWER="answer"
class LLMUsage(BaseModel): model: str; input_tokens: int; cached_input_tokens: int; output_tokens: int; cost_usd: Decimal
class LLMResult[T: BaseModel](BaseModel): data: T; usage: LLMUsage   # PEP 695 generics
class LLMError(Exception)  ·  class LLMOutputInvalid(LLMError)  ·  class BudgetExceeded(LLMError)
class LLMProvider(Protocol):
    async def structured(self, *, task: LLMTask, system: str, cached_context: str,
                         user: str, schema: type[T], max_tokens: int) -> LLMResult[T]: ...
# Model per task comes from config (LLM_MODEL_SCORE=claude-haiku-5-5, LLM_MODEL_TAILOR=claude-sonnet-5-5 …),
# never hard-coded. `cached_context` = profile + rubric → sent with a prompt-cache breakpoint.
# Structured output via tool-use with the JSON schema from schema.model_json_schema(); validate with Pydantic; 1 retry on ValidationError.

# integrations/notify/base.py
class Notification(BaseModel): kind: str; title: str; body: str; link: str|None; priority: Literal["low","default","high"]; dedupe_key: str
class Notifier(Protocol):
    channel: Literal["inapp","push","email"]
    async def send(self, n: Notification) -> None: ...
```

### Application state machine (`domain/state_machine.py`, pure function)
```
queued      → applied | withdrawn | archived
applied     → next_steps | rejected | offer | no_response | withdrawn
next_steps  → next_steps (stage change) | rejected | offer | withdrawn
no_response → next_steps | rejected | offer          (late replies happen)
offer       → accepted | declined
terminal: rejected, withdrawn, accepted, declined, archived
override:   any → any, only with actor="user" and override=True (fixes misclassification); always logged
```
`transition(app: ApplicationState, to, *, actor, stage=None, reason=None, override=False, now=None) -> ApplicationEvent` raises `InvalidTransition`.
Implemented rules (S1-02):
- `withdrawn`, `accepted`, `declined` and `archived` are **user-only targets**. An `email` or `system` actor gets `InvalidTransition`, so an email classifier can never accept or decline an offer.
- `next_steps → next_steps` requires a non-empty `stage` that differs from the current one. Entering `next_steps` from elsewhere may omit `stage`.
- An override to the identical (status, stage) is rejected as a no-op. The service persists the event and emits the Inngest event `application/status.changed`.

### Notification rules matrix (`applications/notify_rules.py`, from the user's spec)
| Transition | In-app | Push | Email |
|---|---|---|---|
| queued/applied/no_response → rejected (normal priority) | ✅ | — | — |
| … → rejected **and application.priority = high** | ✅ | ✅ | ✅ |
| any → next_steps (incl. a new stage) | ✅ | ✅ | ✅ |
| next_steps → rejected | ✅ | ✅ | ✅ |
| any → offer | ✅ | ✅ | ✅ |
| daily quota reached (Phase 3) | ✅ | ✅ | ✅ |
| applied → no_response (auto after 30 d) | digest only | — | — |
Implemented rules (S1-02): a rejection also notifies on all channels when it comes from `offer` (a rescinded offer, via user override). `→ applied` notifies in-app only. `withdrawn`/`accepted`/`declined`/`archived` notify nobody, because they're the user's own actions. Push priority is `high` for next_steps/offer and `default` otherwise.
MVP sends in-app + push only. The email channel arrives in Phase 2, so in the MVP the rules return `email` and the email notifier is a no-op stub that logs.

---

## Database schema (S1-03)
All PKs are `uuid` (server default `gen_random_uuid()`), and every table has `created_at` and `updated_at` as `timestamptz` (UTC).
- **companies**: name, website, priority (`low|normal|high`), status (`active|inactive|invalid`), notes.
- **job_sources**: company_id FK, ats, token, enabled, last_polled_at, last_success_at, consecutive_failures int, last_error text. `UNIQUE(ats, token)`.
- **jobs**: source_id FK, company_id FK, external_id, title, title_normalized, role_family, seniority, department, description_text, description_html, content_hash (sha256 of normalized text+title+location), fingerprint (sha256 of company_id + title_normalized + primary location), location_raw, locations JSONB, workplace_type, employment_type, comp_min, comp_max, comp_currency, comp_interval, apply_url, canonical_url, posted_at, first_seen_at, last_seen_at, closed_at, status (`open|closed`), filter_status (`pending|passed|rejected`), filter_reasons JSONB, user_state (`none|saved|dismissed`), raw JSONB. `UNIQUE(source_id, external_id)`. Indexes: fingerprint, (status, filter_status), first_seen_at.
- **job_matches**: job_id FK, content_hash, profile_version int, rubric_version str, model, prescore float, score int 0–100, subscores JSONB {technical, experience, projects, preferences}, reasoning text, matched_skills JSONB, missing_requirements JSONB, required_skills JSONB, recommended_action (`apply|maybe|skip`), status (`ok|failed`), error. `UNIQUE(job_id, content_hash, profile_version, rubric_version, model)`. This is the cache key.
- **profile** (single row, `id=1`): version int, candidate JSONB (skills, years, education, work_auth, links), preferences JSONB (see S1-10), updated_at. Every save increments the version.
- **resumes**: kind (`master|variant`), parent_id FK self, master_version int, name, role_family, content JSONB (ResumeDoc), keyword_signature JSONB (sorted list), source_job_id FK nullable, model, archived bool.
- **applications**: job_id FK **UNIQUE**, resume_id FK, status, stage text, priority (`normal|high`, defaulting to company.priority), applied_at, last_status_at, notes.
- **application_events**: application_id FK, from_status, to_status, stage, actor (`user|system|email`), reason, override bool, payload JSONB.
- **notifications**: kind, title, body, link, priority, channels JSONB, delivery JSONB {channel: ok|error}, read_at, `dedupe_key UNIQUE`.
- **workflow_runs**: kind, status (`running|ok|partial|failed`), started_at, finished_at, stats JSONB, error.
- **llm_calls** (cost ledger): task, model, input_tokens, cached_input_tokens, output_tokens, cost_usd numeric(10,6), job_id nullable, ok bool.

Job availability (`jobs.status`) and application status are **separate** columns on separate tables. A closed job never touches its application.

---

## Edge cases & mitigations (cheapest effective fix first)
| # | Edge case | Mitigation |
|---|---|---|
| 1 | Same role posted on two ATSes or reposted | `fingerprint` dedupe; newer marked `_duplicate_of`; a reposted job matching a past *application* fingerprint shows an "Already applied {date}" badge and blocks re-queue without `force` |
| 2 | Job closes after you applied | Separate `jobs.status` and `applications.status`; closure never touches applications |
| 3 | Job description edited | `content_hash` change → re-filter and re-score; old match rows kept (versioned history) |
| 4 | Company changes ATS or slug | 3 consecutive failures → disable source + notify; "re-detect" button |
| 5 | Flaky API response omits jobs | Closure only after 2 consecutive misses |
| 6 | Rate limits / 5xx | Typed transient errors, Inngest retries with backoff, per-ATS concurrency 4 |
| 7 | LLM invalid JSON | Forced tool-use + Pydantic validation + 1 repair retry → `status=failed`, retried next run |
| 8 | LLM cost runaway | Deterministic filter → prescore top-K → cache key → daily budget guard → `partial` run status |
| 9 | Prompt injection in job posts | Posting wrapped as untrusted data, scores clamped in code, injection cases in the eval set, LLM output never triggers actions directly |
| 10 | Resume fabrication | Provenance IDs + number/skill subset validator + 422 on failure |
| 11 | Ambiguous location / remote ("Remote – US only") | Normalizer extracts countries; unknown passes the filter but shows an "unverified location" chip |
| 12 | Hourly vs annual, non-USD comp | `interval` + currency stored; salary filter only applied to USD annual (or hourly × 2080); unknown passes |
| 13 | Sponsorship / clearance language | Regex flags; hard filter only for an explicit conflict |
| 14 | Timezones / "today" for quota and budget | Store UTC; compute day boundaries in `prefs.timezone` |
| 15 | Spamming one company | `company_cooldown_days` warning; ≤ 1 per company per day in the quota planner |
| 16 | Fewer than N good jobs | Shortfall reported, relaxation only with approval |
| 17 | Misclassified email (Phase 2) | Confidence gate + review inbox + user override transition, always logged |
| 18 | Duplicate workflow runs | Inngest event IDs + DB unique constraints → every workflow safe to rerun |
| 19 | Model deprecated or swapped | Model id in config and stored on every match/variant; cache key includes the model |
| 20 | PII exposure | Auth before deploy, secrets only in env, no PII in logs, ntfy topic secret, encrypted Gmail token, nightly backups |
| 21 | Huge or HTML-heavy descriptions | `html_to_text` + truncation preserving the requirements section |
| 22 | Master resume edited after variants exist | Variants keep `master_version`; reuse only matches the current version; old variants stay viewable |

## Cost posture (rough)
A Haiku score costs about 3k input tokens (~2k of it cached profile/rubric) plus about 400 output tokens. With prescore top-K = 60, that's about 60 calls per 6-hour cycle at most, and much less once the cache warms (only new or changed jobs are scored). Tailoring with Sonnet is on demand only and reuse skips it entirely. **Starting budget: $1/day, enforced in code.** Hosting: $0 locally; Railway about $5–15/month at MVP scale; Inngest free tier; ntfy free.

## Design direction (MVP placeholder)
Neutral, information-dense "tool" look: Inter/Geist font, an 8px grid, cards with 1px borders rather than shadows, one accent color, and score colors as the only strong color. Dark mode from day one. Everything is token-driven (`globals.css` variables plus the Tailwind theme extension), so a later design direction is a token and component-variant change, not a rewrite.

---
