# Operations

## Required production services

- managed PostgreSQL 17+
- Redis 8+
- object storage (S3-compatible)
- AI provider + optional fallback
- search provider
- Firebase/FCM
- Google Play Developer API credentials for subscription verification
- Sentry or equivalent crash/error tracking
- optional ClamAV
- optional Qdrant for semantic vector retrieval

## Observability

Every API response carries an `X-Request-ID`. Do not log secrets, access tokens, refresh tokens, passwords, file contents or API keys.

Monitor:

- API p50/p95/p99 latency
- 4xx/5xx rate
- AI latency and provider failure rate
- streaming failures
- PostgreSQL pool saturation
- Redis health
- worker queue depth
- storage failures
- subscription verification errors
- AI cost per user and per plan

## Alerts

Start with alerts for 5xx > 2%, AI provider failures > 5%, DB unavailable, Redis unavailable, queue age > 5 minutes, backup failure, and unexpected AI cost spikes.
