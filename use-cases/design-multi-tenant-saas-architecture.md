---
title: "Design Multi-Tenant SaaS Architecture with AI"
slug: design-multi-tenant-saas-architecture
description: "Choose the right multi-tenancy strategy, design tenant isolation at database and application layers, and generate implementation scaffolding."
skills: [saas-architecture-advisor, database-schema-designer]
category: development
tags: [multi-tenant, saas, architecture, database-design, tenant-isolation]
---

# Design Multi-Tenant SaaS Architecture with AI

## The Problem

Converting a single-tenant application to multi-tenant -- or designing multi-tenancy from scratch -- involves dozens of interconnected decisions that compound on each other. Shared database or per-tenant? Row-level security or application-layer filtering? How do you handle tenant-specific customizations without forking the codebase?

One wrong choice at the database layer means a painful migration later. Teams spend weeks researching patterns and still end up with data leakage bugs when a query forgets the `WHERE tenant_id = ?` clause. The worst part: you won't discover the architectural mistake until you have paying customers who can't tolerate downtime for a redesign. A shared-schema approach that works beautifully for 50 tenants can become a compliance nightmare when your first enterprise customer asks "can you prove our data is isolated from other tenants?" during a SOC 2 audit.

## The Solution

Using the **saas-architecture-advisor** and **database-schema-designer** skills, the agent evaluates tenancy strategies against your specific constraints -- tenant count, data sensitivity, compliance needs, team size, and budget -- then generates the schema, middleware, and row-level security policies for the recommended approach.

## Step-by-Step Walkthrough

### Step 1: Evaluate Tenancy Strategies for Your Context

```text
We're building a project management SaaS. Expected: 500 tenants in year 1,
scaling to 5,000. Most tenants are 5-20 users, but 3-5 enterprise clients
need strict data isolation for SOC2. Stack: Node.js, PostgreSQL, Redis.
Monthly budget for infrastructure: $3,000. Recommend a multi-tenancy strategy.
```

Three options surface, each with real tradeoffs:

| Strategy | Pros | Cons | Cost Estimate |
|---|---|---|---|
| **Shared DB, shared schema** (tenant_id column) | Simplest to implement, lowest cost, easy cross-tenant admin queries | Every query needs tenant_id filter, noisy neighbor risk, enterprise clients may reject shared-table audits | ~$400/mo |
| **Shared DB, separate schemas** (PG schemas per tenant) | Strong logical isolation, PostgreSQL handles natively via `search_path`, auditable separation | Schema migrations run per-tenant (500+ on deploy), connection pooling complexity, 5,000 schemas strains pg_catalog | ~$600/mo |
| **Hybrid** -- shared schema for standard + dedicated DB for enterprise | Standard tenants get low cost with RLS, enterprise tenants get full isolation, SOC2-compliant without overengineering | Two code paths for data access (manageable with repository pattern) | ~$1,200-$1,770/mo |

The hybrid approach wins here. 495+ standard tenants share one database with row-level security -- they never notice the difference. The 3-5 enterprise tenants each get a dedicated RDS instance with full isolation -- exactly what their compliance auditors want to see. Total database cost stays within the $3,000 budget with room for application servers and Redis.

The per-schema approach looks appealing on paper, but it doesn't survive contact with 5,000 tenants. PostgreSQL's catalog tables grow linearly with schema count, migration deployments take longer with each new tenant, and connection pooling with per-request schema switching is a source of subtle bugs. It's the right choice at 50 tenants and the wrong one at 5,000.

### Step 2: Generate the Database Schema with Tenant Isolation

```text
Generate the PostgreSQL schema for the hybrid approach. Include the shared
tenant table, row-level security policies, and the middleware pattern for
tenant context injection. Our main entities: projects, tasks, members, comments.
```

The tenant registry lives in the shared database and routes requests to the right place:

```sql
-- Tenant registry (always in shared DB, regardless of tenant tier)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(63) UNIQUE NOT NULL,
    tier VARCHAR(20) NOT NULL DEFAULT 'standard',  -- standard | enterprise
    database_url TEXT,  -- NULL for standard, connection string for enterprise
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Row-level security for shared tables
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON projects
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Same pattern for tasks, members, comments
-- Application sets tenant context per request:
-- SET LOCAL app.current_tenant_id = '<tenant-uuid>';
```

RLS is the critical piece -- and the reason the hybrid approach works so well. Even if application code forgets a `WHERE tenant_id = ?` (and it will -- someone will write a raw SQL query or use an ORM shortcut), PostgreSQL enforces the filter at the database level. Every query, every ORM call, every raw SQL statement gets filtered automatically. The policy acts as a safety net that catches the bugs your code reviews miss.

The `SET LOCAL` is scoped to the current transaction, so it can't leak between requests even in a connection pool. This is important: `SET` (without `LOCAL`) would persist across connections and create a cross-tenant data leak.

The Express middleware handles routing between shared and dedicated databases:

```typescript
// middleware/tenant-context.ts
export async function tenantContext(req: Request, res: Response, next: NextFunction) {
  const tenantSlug = req.headers['x-tenant-id'] || req.subdomains[0];
  const tenant = await tenantCache.get(tenantSlug);

  if (!tenant) return res.status(404).json({ error: 'Tenant not found' });

  if (tenant.tier === 'enterprise' && tenant.databaseUrl) {
    // Enterprise tenants get their own database -- full isolation
    req.db = getEnterprisePool(tenant.databaseUrl);
  } else {
    // Standard tenants share the database with RLS protection
    req.db = sharedPool;
    await req.db.query("SET LOCAL app.current_tenant_id = $1", [tenant.id]);
  }

  req.tenant = tenant;
  next();
}
```

The `tenantCache` layer is essential -- without it, every request would hit the tenants table. A 60-second Redis TTL keeps routing fast without stale data. When a tenant upgrades from standard to enterprise, the cache expires naturally within a minute.

### Step 3: Add Tenant-Aware Data Access Patterns

```text
Generate a repository pattern that works transparently with both shared and
dedicated databases. Include examples for CRUD operations on projects and
handling tenant-specific feature flags.
```

The repository pattern abstracts the two data paths behind a single interface. Controllers never know whether they're talking to the shared database or a dedicated instance -- the middleware already injected the right connection via `req.db`. This means no `if (tenant.tier === 'enterprise')` checks scattered through business logic.

Feature flags live in the tenant's `settings` JSONB column, so enterprise clients can enable beta features or customize behavior without affecting anyone else. The settings column also handles tenant-specific configuration like timezone preferences, notification schedules, and branding overrides -- all without schema changes.

### Step 4: Generate Tenant Onboarding and Offboarding Flows

```text
Create the tenant provisioning flow: when a new enterprise tenant signs up,
automatically create their dedicated database, run migrations, and configure
the routing. Include cleanup for tenant deletion with data export.
```

Enterprise provisioning becomes a single admin API call that orchestrates the full setup: create the RDS instance, wait for it to become available, run the complete migration suite, seed default data (roles, permissions, sample workspace), update the tenant registry with the connection string, and warm the routing cache. The whole process takes about 4 minutes, and it's idempotent -- safe to retry if it fails halfway through.

Standard tenant provisioning is instant: insert a row in the tenants table and the RLS policies handle everything else. No database creation, no migration runs, no infrastructure provisioning. A standard tenant goes from signup to usable workspace in under 2 seconds.

Offboarding follows a careful sequence: export all tenant data to a timestamped S3 archive, generate a data inventory manifest, notify the tenant's admin that their export is ready, wait 30 days for retrieval, then tear down the dedicated instance (enterprise) or delete the rows with RLS disabled (standard). The tenant record is tombstoned -- never hard-deleted -- in case of legal holds, accidental deletion, or reactivation. The S3 archive is retained for 90 days, then auto-deleted by lifecycle policy.

## Real-World Example

Marta, lead engineer at a 15-person startup building a client portal for accounting firms, faced a classic dilemma. Their app worked great for 20 beta clients on a single database. But their first enterprise prospect -- a 200-person firm -- required contractual data isolation for their compliance audit. "We need to be able to tell our auditors that our data lives in a separate database," the firm's CTO wrote. Rebuilding the entire data layer felt like a month-long project that would delay the enterprise deal and stall the standard-tier growth.

The hybrid approach changed the timeline entirely. Shared database with PostgreSQL RLS for standard tenants, dedicated databases for enterprise -- and a repository pattern that abstracted the two paths so the application code stayed clean. The two-path architecture added about 200 lines of middleware and repository code, not the months-long rewrite the team feared.

The critical moment came during testing: RLS policies caught two existing queries that were missing tenant filters. Without the policies, one firm's project list could have leaked into another's dashboard. Those bugs had been there since launch, invisible because beta clients happened to have unique project names. In production with 500 tenants, it would have been a matter of time before someone saw another firm's data.

The hybrid architecture launched within 3 weeks, supporting 120 standard tenants and 2 enterprise clients, with infrastructure costs under $1,500/month. The enterprise compliance audit passed on the first try -- the auditor spent 15 minutes verifying the dedicated database and moved on. Six months later, the platform serves 340 standard tenants and 4 enterprise clients without a single tenant isolation incident.
