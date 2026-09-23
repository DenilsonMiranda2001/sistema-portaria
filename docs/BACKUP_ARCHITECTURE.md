# ControleID — PostgreSQL backup foundation

Status: code foundation only; **not operational until a staging restore drill succeeds**.

## Isolation and security

Use a separate Railway cron service/job, never the web service. The job needs
PostgreSQL client utilities `pg_dump` and `pg_restore` matching the server's
major version (the current Railway Postgres image reports version 18).
Install them in the backup job image; the current web Railpack image is **not**
assumed to contain them. Use a private dedicated Cloudflare R2 bucket and a
backup-only API token; do not reuse the operational media bucket or credentials.
Never make backup objects public. Do not put secrets in GitHub or logs.

Required environment variables (configure **only on the backup job**):
`BACKUP_DATABASE_URL` (reference the Postgres in the same Railway environment),
`BACKUP_R2_ENDPOINT` (HTTPS account S3 endpoint),
`BACKUP_R2_BUCKET`, `BACKUP_R2_ACCESS_KEY_ID`,
`BACKUP_R2_SECRET_ACCESS_KEY`, `BACKUP_ENVIRONMENT=staging|production`,
`BACKUP_CONFIRM_ISOLATED_BUCKET=yes`. Command:
`python -m scripts.backup_postgres_r2`.

## Format and recovery

The job produces a PostgreSQL custom-format dump and a JSON manifest containing
SHA-256, byte length, timestamp, and object key. It validates the local archive
with `pg_restore --list` and checks remote object length before publishing the
manifest. A manifest indicates upload success, **not** proven recoverability.
Object storage encryption and access policies must be checked in the R2 account.
Do not enable automatic deletion/retention before successful restore testing.

Restore drill: download dump from the manifest, verify SHA-256, create a
**new isolated PostgreSQL database**, run `pg_restore --no-owner --no-acl
--exit-on-error`, validate migration ledger and tenant integrity, then run
authenticated application smoke against the restored database. Never point a
restore command at the active production database. Record elapsed restore time.

Initial proposed schedule: daily; proposed retention: 7 daily and 4 weekly,
to be implemented only after recovery testing. Daily backups alone can lose up
to 24 hours of data. Media files stored outside PostgreSQL require their own
independent backup and consistency policy. PITR/WAL archival is a later decision
if the accepted recovery point becomes shorter than 24 hours.

## Release gate

1. Isolated staging job completes and publishes manifest.
2. Download and verify digest, restore into a separate staging database.
3. Verify migration ledger, data integrity, tenant separation, authenticated flows.
4. Only then configure production schedule, alerts, retention and recovery runbook.
