# Backup and Recovery

The repository includes PostgreSQL backup and restore scripts plus a scheduled GitHub workflow.

## Backup

`pg_dump --format=custom --no-owner` is uploaded to encrypted S3 storage.

## Verification

Production must periodically restore the newest dump into an isolated database and run migrations/integrity checks. A backup that has never been restored is not considered verified.

## Recovery targets

Define business values before launch:

- RPO: recommended initial target <= 24h, lower for paid production if required.
- RTO: recommended initial target <= 4h.

For higher availability, use managed PostgreSQL point-in-time recovery and cross-region replicas.
