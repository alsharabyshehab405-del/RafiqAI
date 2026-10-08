# Deployment

## Environments

Use separate credentials and databases for development, staging and production.

Never point staging at production data.

## API

1. Build the backend container.
2. Run `alembic upgrade head` as a controlled deployment step.
3. Start multiple stateless API replicas behind HTTPS.
4. Start ARQ workers separately.
5. Configure health and readiness probes.
6. Restrict CORS to trusted application origins.

## Zero-downtime migrations

Migrations must be backward-compatible with the previous application version before removing old columns or contracts.

## Rollback

Application rollback is preferred over destructive database rollback. Forward-fix migrations are preferred after a schema has been used by production.

## Replit deployment

RafiqAI can run its existing FastAPI backend on Replit without changing the backend architecture.

### Startup command

The repository includes `.replit` with the following runtime flow:

```text
python -m pip install -r backend/requirements.txt && cd backend && alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Replit supplies `PORT` at runtime. The backend binds to `0.0.0.0` and does not hardcode a production port.

### Environment / Secrets

Copy the names from `.env.example` into Replit Secrets / Environment Variables. Do not commit real values. In particular, `DATABASE_URL`, `JWT_SECRET`, AI provider keys, `QDRANT_API_KEY`, object-storage credentials, Firebase/Google credentials, and `ADMIN_BOOTSTRAP_TOKEN` are server-side secrets.

`DATABASE_URL` must point to the real PostgreSQL service. SQLite is not a production substitute.

`RATE_LIMIT_STORAGE_URI` must point to the real Redis service for production worker/rate-limit operation.

`QDRANT_URL` and `QDRANT_API_KEY` are required for hybrid/vector RAG. Without them, the existing backend remains lexical-only according to its current configuration.

### Health and readiness

- `GET /health` is a lightweight health endpoint and does not expose credentials.
- `GET /ready` performs a database query and therefore requires the configured PostgreSQL service.

### Migrations

Run from the repository root:

```text
cd backend && alembic upgrade head
```

The Replit startup command runs this migration step before starting FastAPI. PostgreSQL is required for the real deployment.

### Worker

The existing ARQ worker remains a separate process:

```text
cd backend && arq app.worker.WorkerSettings
```

Do not replace Redis/ARQ with an in-process fake. A production deployment that needs agents, research, and automations must provide a real Redis service and a separately running worker process. This is **REQUIRES REAL ENVIRONMENT** unless a second Replit process/deployment is configured.

### External services

The following remain external dependencies and are not replaced by local fakes:

- PostgreSQL — REQUIRES REAL ENVIRONMENT
- Redis/ARQ — REQUIRES REAL ENVIRONMENT
- Qdrant — REQUIRES REAL ENVIRONMENT
- AI providers — REQUIRES REAL ENVIRONMENT / SECRET
- Object storage — REQUIRES REAL ENVIRONMENT / SECRET when enabled
- FCM / Google Play credentials — REQUIRES REAL ENVIRONMENT / SECRET when enabled
