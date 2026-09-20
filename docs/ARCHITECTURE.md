# Sistema Portaria — architecture baseline

## Goal
Evolve the application into a production-ready, multi-tenant condominium platform without mixing data between condominiums.

## Non-negotiable boundaries
- PostgreSQL is the source of truth.
- No secrets, local databases, virtualenvs or uploaded media in Git.
- Production configuration comes from environment variables.
- Schema changes must move to versioned migrations; application startup must not mutate the schema.
- Every business record must ultimately belong to a tenant (condominium), directly or through a tenant-owned parent.
- Authorization is server-side and deny-by-default.
- Photos/documents must use persistent object storage, not Railway's ephemeral filesystem.
- Sensitive operations must be auditable.
- Health checks, structured logs, tests and backup/restore verification are release gates.

## Target domain
Condominio -> Usuarios/Papeis -> Unidades -> Moradores -> Visitantes/Visitas -> Encomendas -> AuditLog.

## Delivery gates
1. Repository/secrets hygiene.
2. Production config + WSGI + health/readiness.
3. Versioned migrations.
4. Tenant model and tenant-scoped constraints/queries.
5. Authorization and CSRF/session hardening.
6. Persistent media storage.
7. Audit log and observability.
8. Automated tests: auth, permissions, tenant isolation, core workflows.
9. Railway PostgreSQL + web service.
10. Backup/restore proof and authenticated production smoke tests.

Do not deploy real personal data until gates 1-8 pass.
