# Tenant RBAC release gate — 2026-09-23

## Verified in isolated CI

- Fresh PostgreSQL 16 bootstrap, migration upgrade, second upgrade (idempotence).
- Upgrade of a separate database containing legacy `admin` and `funcionario` accounts.
- Canonical role conversion and rejection of `platform_admin` in tenant users.
- Delivery tenant foreign key and rejection of a cross-tenant courier association.
- Static quality, unit tests, dependency audit, security static analysis.

These checks establish behavior in CI, **not** readiness of the existing production dataset.

## Observed deployment topology

Railway project `sistema-portaria` currently exposes only a `production` environment. Its web service deploys from GitHub branch `hardening/saas-architecture`, runs `python -m migrations.migrate upgrade` as a **pre-deploy command**, and uses `/readyz` as the health check. The PostgreSQL service has a persistent volume. An environment patch is reported as staged; inspect and reconcile it before making deployment changes.

**Merging PR #5 into its current base branch can trigger production deployment and its database migration.** A green pull-request CI must not be treated as permission to merge.

## Mandatory production release sequence

1. Inspect the current production deployment, pending Railway configuration changes and branch settings. Do not accept staged changes without understanding them.
2. Confirm a recent PostgreSQL backup and **test restore to a separate database**; record backup identifier, restore duration, checksum/integrity checks and the responsible operator. Do not use production for the restore test.
3. Create an isolated staging environment/database, or restore a sanitized production snapshot to an isolated PostgreSQL instance. Confirm its migration history and data anomalies before applying the candidate migration.
4. Run `python -m migrations.migrate upgrade` on the isolated restored copy. Validate legacy role counts, unexpected role values, last-active-admin invariant, delivery foreign keys, orphan tenant references and application compatibility.
5. Run authenticated smoke tests with platform administrator, tenant administrator, administrative operator and concierge accounts; verify unauthorized and cross-tenant requests are rejected, and visitor/access/parcel flows still work.
6. Agree on a maintenance window and database recovery plan. Migration 0020 is forward-only: rolling application code back to a version that expects only legacy roles is **not** a safe database rollback.
7. Only then merge to the production-tracked branch, observe the Railway pre-deploy migration and readiness checks, verify the deployed commit, and repeat authenticated smoke tests. Watch application errors, latency and database health.
8. If any gate fails, stop release and preserve the existing deployment. For a migration already committed, use a tested compatible forward fix or the previously verified database restore plan; do not improvise a destructive reverse migration.

## Current decision

PR #5 remains draft and production remains unchanged until staging and recoverable backup/restore are verified. This document records the release dependency; it does not claim those external gates have passed.
