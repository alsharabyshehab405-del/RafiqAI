# RafiqAI — Global Production Next-Generation

RafiqAI is an Arabic-first, multilingual personal AI platform upgraded **in place** from the existing Global Production Release. The project was not rebuilt from scratch and existing authentication, Room/PostgreSQL, billing, files, notifications, tasks, admin, CI and security foundations are retained.

## Platform capabilities

- Multi-model AI routing, fallback, retry, circuit breaker, context management and cost ledger.
- Streaming chat and structured/tool-call interfaces.
- User-approved persistent memory separated from chat history.
- Projects with isolated context and project-linked conversations.
- Agent orchestration with plan/step state, tool allowlists, budgets, retries, cancellation and audit records.
- Deep Research pipeline: search, fetch, deduplicate, rank, source attribution.
- Files in object storage with type validation, archive safety checks, optional ClamAV and text extraction.
- RAG primitives: parsing, semantic chunking, metadata and lexical retrieval; optional embedding/vector provider configuration.
- Artifacts workspace primitives for documents, notes, tables, code and Markdown.
- Automation records and worker foundation.
- Global search across conversations, messages, projects, files, memories and tasks.
- Google Play subscriptions with server-side verification and plan entitlements.
- FCM notifications, analytics controls, audit logs, metrics and Sentry adapter.
- PostgreSQL, Redis, workers, Docker, backup/restore and CI/CD.
- Arabic/English resources with extensible localization architecture.

## Security principles

- No AI/search/storage/billing secrets in Android.
- Web pages, files, memories and search results are untrusted context.
- Tool execution is allowlisted and budgeted.
- Sensitive actions require an approval path in the agent engine.
- Ownership checks protect user resources.
- Refresh tokens are rotated and revoked.
- Logs avoid passwords, tokens, API keys and private file contents.

## Repository

```text
app/                    Android application
backend/                FastAPI + services + migrations + worker
admin/                  Separate admin surface
docs/                   Architecture, operations, security and release guides
.github/workflows/      CI/CD, security, integration and backup
scripts/                Backup/restore and secret checks
```

## Required server environment

At minimum configure:

```text
DATABASE_URL
JWT_SECRET
AI_BASE_URL
AI_API_KEY
AI_MODEL
AI_PRO_MODEL
AI_PREMIUM_MODEL
RATE_LIMIT_STORAGE_URI
```

For the full commercial platform also configure the appropriate search, object storage, Firebase, Google Play, Sentry and optional embedding/vector variables documented in `.env.example` and `docs/`.

## GitHub verification

The repository includes workflows for:

- Backend + PostgreSQL + Redis tests
- Android Debug build + unit tests + emulator tests
- Security scanning
- Docker integration
- Signed Release APK + AAB
- Container publishing
- Scheduled PostgreSQL backups

A release must not be treated as verified until the GitHub workflows actually pass.

## Verification status

See `docs/PRE_RELEASE_READINESS.md` for the current release gate and `docs/VERIFICATION_REPORT.md` for the earlier verification record.

The Android project uses AGP 9.0.1 with Gradle 9.1.0 in CI, compileSdk/targetSdk 36, minSdk 26, release R8 shrinking, and optional CI signing. The repository currently does not contain a Gradle Wrapper, and this execution environment has no Android SDK or Gradle executable, so an APK/AAB build is **BLOCKED / REQUIRES REAL ENVIRONMENT** here.

The backend declares all runtime/test dependencies in `backend/requirements.txt`, including `slowapi`. CI installs that file before running tests. The local environment used for this release gate has no network access to install missing packages, so full backend pytest remains **BLOCKED** locally when `slowapi` is unavailable.

## Mobile-only release

1. Create a GitHub repository from this project.
2. Upload the project contents, preserving `.github/`.
3. Add the required GitHub Secrets/Variables.
4. Run Backend CI, Android Debug, Security and Integration workflows.
5. Fix any red workflow before release.
6. Run Android Release APK + AAB. The release workflow compiles unsigned when signing credentials are absent and marks the result `SIGNING BLOCKED`; signed Play release still requires the keystore secrets.
7. Download the AAB artifact.
8. Upload it to Google Play Internal Testing.
9. Test billing, account deletion, memory, files, tasks, notifications and offline behavior on a real phone.
10. Promote gradually to Production.

## Documentation

- `docs/ARCHITECTURE.md`
- `docs/AI_PROVIDER.md`
- `docs/DEPLOYMENT.md`
- `docs/OPERATIONS.md`
- `docs/BACKUP_RESTORE.md`
- `docs/SUBSCRIPTIONS.md`
- `docs/DATA_SAFETY.md`
- `docs/TESTING.md`
- `docs/RELEASE_RUNBOOK.md`
- `docs/GOOGLE_PLAY.md`
- `docs/VERIFICATION_REPORT.md`

## Replit

The current backend is prepared for Replit without changing its architecture. Use the repository's `.replit` configuration; its startup flow installs `backend/requirements.txt`, runs `alembic upgrade head`, then starts `uvicorn app.main:app` on Replit's `$PORT`.

Required production values belong in Replit Secrets / Environment Variables. Start with `.env.example` and provide a real PostgreSQL `DATABASE_URL`, Redis `RATE_LIMIT_STORAGE_URI`, `JWT_SECRET`, AI provider credentials, and any Qdrant/object-storage/FCM/Google credentials required by the enabled existing functionality.

Health endpoints:

- `GET /health` — process health without sensitive output.
- `GET /ready` — database readiness check.

The ARQ worker remains separate and must run with `cd backend && arq app.worker.WorkerSettings` against a real Redis service. PostgreSQL, Redis/ARQ, Qdrant, AI providers, object storage, and device/Android verification remain **REQUIRES REAL ENVIRONMENT** where applicable.
