# Tenant RBAC Architecture

## Security boundaries

Portaria Control has two authorization planes:

1. **Platform control plane** — accounts in `platform_admins`. They administer tenants and are not tenant users.
2. **Tenant plane** — accounts in `usuarios`, always bound to exactly one `condominio_id` in the current product model.

Authentication answers **who the actor is**. Tenant context answers **which condominium the request belongs to**. RBAC answers **what the actor may do**.

## Roles

| Role | Scope | Purpose |
|---|---|---|
| `platform_admin` | Platform | SaaS owner/control plane |
| `admin_condominio` | One condominium | Tenant administration, users, audit and privileged tenant operations |
| `administrativo` | One condominium | Day-to-day administrative/operational workflows |
| `porteiro` | One condominium | Portaria operational workflows |

The platform administrator is intentionally stored separately from tenant users. Tenant routes must never infer authorization only from UI visibility; every sensitive route requires server-side RBAC and every repository mutation remains tenant-scoped.

## Migration compatibility

Migration `0020_tenant_rbac_roles.sql` converts legacy roles:

- `admin` -> `admin_condominio`
- `funcionario` -> `porteiro`

The authorization layer temporarily canonicalizes the legacy values so rolling deployments and old sessions fail safely while the database migration is being applied.

## Invariants

- A tenant user belongs to one condominium in the current model.
- A tenant administrator cannot manage a user from another condominium.
- A condominium must retain at least one active `admin_condominio`.
- `administrativo` and `porteiro` cannot manage tenant users or tenant audit settings.
- Platform administrators are redirected to the platform console and do not silently enter tenant operations.
- Tenant identity is revalidated on every request.
- Authorization is enforced in routes and tenant ownership is enforced again in database operations.

## Future evolution

If a future management company needs one human identity across multiple condominiums, introduce a dedicated membership relation rather than overloading `usuarios.condominio_id`. That migration should be performed as a separate identity-model change with explicit data migration and authorization tests.

## Release gate

1. Verify a recoverable PostgreSQL backup before any production migration.
2. Run migration 0020 on a database clone with representative existing `admin` and `funcionario` accounts. Verify their role conversion and the checksum recorded in `schema_migrations`.
3. Verify a new installation uses the same role constraint as the upgraded database.
4. Exercise authenticated tenant and platform sessions, cross-tenant URL attempts, admin demotion, deactivation and simultaneous last-admin mutations.
5. Confirm tenant audit events, user creation, password reset and operational routes remain functional.
6. Merge only after CI and staging checks; deploy with rollback and recovery plan. The migration is forward-only; reverting application code without a compatible role strategy is not a safe rollback.

Tenant administrator demotion and deactivation acquire a lock on the condominium row before checking the last-active-admin invariant; the platform-side deactivation path takes the same lock.
