#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL is required}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$BACKUP_DIR/rafiq-$STAMP.dump"
pg_dump "$DATABASE_URL" --format=custom --file="$OUT"
find "$BACKUP_DIR" -type f -name 'rafiq-*.dump' -mtime "+$RETENTION_DAYS" -delete
printf 'Backup created: %s\n' "$OUT"
