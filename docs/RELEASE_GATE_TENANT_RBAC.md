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

## Candidate validation added to the quality gate

- `scripts/ci_authenticated_smoke.py` exercises real login, tenant session identity, foreign-tenant visitor/parcel access, a denied foreign-tenant mutation, role separation and session revocation on a disposable PostgreSQL database.
- `scripts/isolated_release_preflight.py` performs read-only role, tenant association, active-administrator and foreign-key checks. It refuses to run unless `APP_ENV=test|staging`, `ALLOW_ISOLATED_PREFLIGHT=yes` and an explicit database URL are supplied. Its database-name guard is a secondary safeguard, **not** a substitute for verifying the actual staging connection.
- Both scripts run after the PostgreSQL migration tests. A green run validates the isolated CI dataset only. Repeat the preflight on a representative isolated restored/sanitized staging dataset before production release.

## Deployment preparation (not execution)

1. Confirm the exact candidate commit, Railway tracked branch and pending configuration changes. Keep the production-tracked branch unchanged until release approval.
2. Record the schema_migrations state and row counts for condominiums, users, visitors, visits, lots and parcels in the isolated staging dataset. Review all preflight anomalies before migration.
3. After migrating staging, run the authenticated smoke and preflight. Verify that role conversion and tenant relationships preserved the expected records.
4. Before production merge, require a proven restore and a recovery decision for forward-only role migration. An application rollback alone may be incompatible with migrated roles.
5. On deployment, verify migration logs, readiness, deployed commit, login for each role, foreign-tenant denials and parcel/visitor flows. Halt further changes on any failed gate.
