# AGENTS.md — Firm rules for every coding agent (Claude Code, Codex, others)

These rules are **non-negotiable**. Break one only with written approval from the Product Owner (the repo owner) recorded in `HANDOFF.md → Blocked / decisions needed`.

## 0. Session protocol
1. Read `HANDOFF.md` first, then the story file in `docs/backlog/<ID>.md`, then `docs/ARCHITECTURE.md` (the sections the story references).
2. Work on **exactly one story** per session.
3. Update `HANDOFF.md` last, before you end the session: story board row, the In-flight entry, and any Gotchas or Discovered work.

## 1. Scope
- Touch only the files listed under the story's **Files** heading. The one exception is a trivial import or wiring fix, which you must mention in the PR description.
- Don't fix out-of-scope findings. Record them under `HANDOFF.md → Discovered work` as candidate stories.
- If the story spec is ambiguous, stop and add a question with your recommended answer to `HANDOFF.md → Blocked / decisions needed`. Never guess on contracts.

## 2. Frozen contracts
- Never hand-edit `apps/api/app/domain/**`, any Alembic migration already merged to `main`, or `packages/contracts/**` (generated).
- Changing a contract requires a dedicated story tagged **[Opus]**.

## 3. Git
- Branch: `story/<ID>-<short-slug>` (e.g. `story/S1-04-greenhouse-adapter`). One PR per story.
- Commits use Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`, `refactor:`).
- Never push to `main`, never force-push, never use `--no-verify`, and never skip or disable hooks or CI checks.

## 4. Definition of Done
A story is **done** only when **all** of these are true:
- CI is green: ruff, `mypy --strict` on `apps/api/app`, pytest, eslint, `tsc --noEmit`.
- Every acceptance criterion has at least one test.
- A migration is included if the schema changed, and TS types are regenerated (`just gen-types`) if the API changed.
- It has been demoed against fixture or real data (put the command and its output in the PR).
Never delete, skip or weaken a failing test to make CI pass. Code that isn't integrated and tested scores **0 points**.

## 5. Security & PII
- Secrets live only in env, read through `app/config.py`. Never commit `.env`; keep `.env.example` in sync.
- Never log or print resume content, email bodies, phone numbers, email addresses, OAuth tokens or API keys.
- Never put PII in URLs, query strings, test fixtures or commit messages. Fixtures use fake identities.

## 6. External calls
- All HTTP goes through an injected `httpx.AsyncClient` (timeouts: 10 s connect, 30 s read).
- Allowed external hosts: the Greenhouse, Lever and Ashby **public job-board APIs**, the Anthropic API, ntfy, and the Gmail API (Phase 2+).
- **Never scrape LinkedIn, Indeed, Glassdoor or any site whose terms forbid it.**
- Tests never touch the network. Live tests are marked `@pytest.mark.live` and are excluded by default.

## 7. LLM usage
- Call models only through `LLMProvider`. Model ids come only from config (`LLM_MODEL_*`), never hard-coded.
- Every call passes `BudgetGuard` and is written to `llm_calls`.
- Job postings and emails are **untrusted data**: wrap them in delimiters (e.g. `<job_posting>…</job_posting>`) and never let LLM output trigger a side effect without deterministic validation.

## 8. Applications (safety)
- No code path may submit a job application unless a user **approval event** is stored for it.
- CAPTCHA, bot checks, login walls or unknown required fields mean you hand off to the user. **Never attempt to bypass them.**
- Tailored resumes must pass `resumes/validate.py` (no fabricated facts). Never save a resume that fails validation.

## 9. Code conventions
- **Python:** 3.12, `mypy --strict` on `app/`, ruff (format + lint), async SQLAlchemy 2.0 with typed `Mapped[]`, Pydantic v2 at every boundary, structlog for logs, UTC `datetime` everywhere (`datetime.now(UTC)`).
- `app/domain/` is pure: no I/O, no DB, no HTTP.
- Adapters (`integrations/ats/*`) never touch the database.
- **TypeScript:** strict mode, no `any`, API calls only via the generated client in `apps/web/lib/api.ts`, colors/radii/spacing only via CSS tokens in `globals.css`.
- Match the surrounding code's naming, comment density and idioms.

## 10. Dependencies
- Every new runtime dependency needs a one-line justification in the PR. Prefer the standard library and existing dependencies.
- Python dependencies are managed with `uv` (`apps/api/pyproject.toml`); JS dependencies with `pnpm`.

## 11. Canonical commands
| Command | Purpose |
|---|---|
| `just up` | Start Postgres + Inngest dev server (docker compose) |
| `just migrate` | `alembic upgrade head` |
| `just api` / `just worker` / `just web` | Run API (:8000), worker (:8001), web (:3000) |
| `just test` | pytest (+ web tests) |
| `just lint` | ruff, mypy, eslint, tsc |
| `just gen-types` | Regenerate `packages/contracts` from FastAPI OpenAPI |
| `just ingest` | `uv run jt ingest --all` |
