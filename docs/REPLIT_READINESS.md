# RafiqAI — Replit Readiness

## Scope

This pass prepares the existing RafiqAI backend for Replit only. No new product feature, backend subsystem, fake service, or architectural rewrite was introduced.

## Replit configuration files changed

- `.replit` — selects Python 3.12 and runs the existing dependency install + startup flow.
- `replit.nix` — provides the existing Python 3.12/PostgreSQL runtime packages.
- `scripts/start-replit.sh` — runs the existing Alembic migrations and starts the existing FastAPI application on Replit's `PORT`.
- `.env.example` — complete environment-variable template with secret placeholders only.
- `docs/DEPLOYMENT.md` — Replit deployment/runbook details.
- `README.md` — Replit startup and external-service notes.

## Startup command

The Replit run command is:

```text
python -m pip install -r backend/requirements.txt && ./scripts/start-replit.sh
```

The startup script runs:

```text
cd backend
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
```

`PORT` is supplied by Replit at runtime. A local fallback of `8000` exists only for direct script execution; it is not a production hardcoded port.

## Health endpoints

- `GET /health` — process health; returns only status/service/version.
- `GET /ready` — database readiness check using the configured SQLAlchemy database connection.

The existing `/health` endpoint was retained; no new health feature was added.

## Migration command

```text
cd backend && alembic upgrade head
```

The Replit startup flow executes this command before FastAPI starts.

## Required environment variables

See `.env.example`. The important production values are:

- `DATABASE_URL` — real PostgreSQL URL.
- `JWT_SECRET` — Replit Secret.
- `AI_BASE_URL`, `AI_API_KEY`, model/provider settings — real AI provider configuration.
- `RATE_LIMIT_STORAGE_URI` — real Redis URL for production rate limiting/worker queue use.
- `QDRANT_URL`, `QDRANT_API_KEY` — real Qdrant configuration for hybrid/vector RAG.
- `CORS_ORIGINS` — trusted HTTPS origins.
- Object-storage variables (`S3_*`) when object storage is enabled.
- Firebase / Google Play service credentials when those existing integrations are enabled.
- `ADMIN_BOOTSTRAP_TOKEN` and other administrative secrets when used.

No real secret is included in the repository.

## Tests actually executed

- Replit TOML/config parse — **PASS**.
- Startup script shell syntax — **PASS**.
- Environment-template completeness against `Settings` fields — **PASS**; no missing settings fields.
- Existing final/regression suite — **41 passed**.
- Python compilation — **PASS** before final artifact cleanup.
- SQLite-only Alembic validation (`upgrade -> downgrade 0001 -> upgrade head`) — **PASS**.
- Secret/artifact scan — **PASS** after cleanup.
- `/health` route existence/static verification — **PASS**.

## Blocked tests

- `pip install -r backend/requirements.txt` — **BLOCKED** in this execution environment because outbound package-index DNS/network access is unavailable.
- Full `pytest` — **BLOCKED** because `slowapi` is not installed locally and dependency installation could not reach the package index.
- FastAPI live startup — **BLOCKED** by the same missing runtime dependencies (`slowapi`, `psycopg` in this environment).
- Real PostgreSQL migration — **REQUIRES REAL ENVIRONMENT**.
- Real Redis/ARQ — **REQUIRES REAL ENVIRONMENT**.
- Real Qdrant — **REQUIRES REAL ENVIRONMENT**.
- Real AI providers — **REQUIRES REAL ENVIRONMENT / SECRET**.
- Object storage — **REQUIRES REAL ENVIRONMENT / SECRET** when enabled.
- Android/device integration with the Replit backend — **REQUIRES REAL DEVICE / LIVE BACKEND**.

## External services required

The existing architecture remains dependent on real external services where configured:

- PostgreSQL — **REQUIRES REAL ENVIRONMENT**
- Redis / ARQ — **REQUIRES REAL ENVIRONMENT**
- Qdrant — **REQUIRES REAL ENVIRONMENT**
- OpenAI-compatible / Anthropic / Gemini providers — **REQUIRES REAL ENVIRONMENT / SECRET**
- S3-compatible object storage — **REQUIRES REAL ENVIRONMENT / SECRET** when enabled
- Firebase / Google Play — **REQUIRES REAL ENVIRONMENT / SECRET** when enabled

No fake replacement was added.

## Worker note

The existing ARQ worker remains a separate process:

```text
cd backend && arq app.worker.WorkerSettings
```

The web process does not silently replace the worker. A Replit deployment that requires agents, research, and automations must provide a separate worker process/deployment backed by real Redis.

## Remaining blockers

1. Replit/live dependency installation must be performed in the actual Replit environment.
2. A real PostgreSQL database must be configured and migrated.
3. A real Redis service and separate ARQ worker process must be configured for background jobs.
4. AI provider credentials must be supplied as Replit Secrets.
5. Qdrant credentials must be supplied for hybrid RAG.
6. Any enabled object-storage/Firebase/Google Play integrations require their real credentials.
7. Live `/health`, `/ready`, authentication, chat, CORS, and error-path verification must be performed after deployment.

## Release statement

This pass prepares the current backend for Replit configuration and startup. It does **not** claim that the backend is live or production-verified on Replit. Live verification remains **REQUIRES REAL ENVIRONMENT**.
