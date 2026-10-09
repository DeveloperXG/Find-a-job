# Works from PowerShell and Git Bash on Windows, and from sh on Linux/macOS.
set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

default:
    @just --list

# Start Postgres + Inngest dev server
up:
    docker compose -f infra/docker-compose.yml up -d --wait postgres
    docker compose -f infra/docker-compose.yml up -d inngest

down:
    docker compose -f infra/docker-compose.yml down

# alembic upgrade head (a no-op until S1-03 adds the first migration)
[working-directory: 'apps/api']
migrate:
    {{ if path_exists("apps/api/alembic.ini") == "true" { "uv run alembic upgrade head" } else { "echo 'no alembic.ini yet (arrives with S1-03); nothing to migrate'" } }}

[working-directory: 'apps/api']
api:
    uv run uvicorn app.main:app --reload --port 8000

[working-directory: 'apps/api']
worker:
    uv run uvicorn app.worker:app --reload --port 8001

web:
    pnpm --filter web dev

test: test-api test-web

[working-directory: 'apps/api']
test-api:
    uv run pytest

# Web "tests" are a production build until S3-02 adds Playwright
test-web:
    pnpm --filter web build

lint:
    uv --directory apps/api run ruff check .
    uv --directory apps/api run ruff format --check .
    uv --directory apps/api run mypy
    pnpm lint
    pnpm typecheck

# Regenerates packages/contracts from FastAPI's OpenAPI (wired up in S1-11)
gen-types:
    echo 'gen-types arrives with S1-11 (openapi-typescript + openapi-fetch)'

[working-directory: 'apps/api']
ingest:
    uv run jt ingest --all