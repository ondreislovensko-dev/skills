---
title: "Create an API Versioning Strategy with AI"
slug: create-api-versioning-strategy
description: "Design and implement API versioning that lets you evolve your API without breaking existing client integrations."
skills: [coding-agent, api-tester, markdown-writer]
category: development
tags: [api-versioning, api-design, backward-compatibility, migration, rest-api]
---

# Create an API Versioning Strategy with AI

## The Problem

Your REST API has 30 active endpoints consumed by a mobile app, three partner integrations, and a public developer community. You need to redesign the user endpoint to support team-based accounts, but changing the response shape will break every existing client.

The last time you made a breaking change, you just updated the endpoint and emailed partners. Two integrations broke silently, one partner churned, and the mobile app crashed for users who had not updated. The team still argues about URL versioning versus header versioning, and nobody wants to maintain two complete copies of every controller.

The stakes are higher this time: 200 active API consumers, a mobile app that cannot force-update (half the users are on versions from six months ago), and partners whose integration code was written by contractors who are long gone. The wrong approach will cost customers, partners, and the team's credibility.

## The Solution

Using the **coding-agent**, **api-tester**, and **markdown-writer** skills, the agent implements URL-path versioning with response transformers that keep business logic in one place, generates backward compatibility tests, and writes migration documentation with code examples in three languages.

## Step-by-Step Walkthrough

### Step 1: Describe the API and the Breaking Change

```text
Our Express REST API has 30 endpoints. Current base: /api/v1/
We need to introduce v2 of the user endpoints because we're adding
team-based accounts. The changes:
- GET /users/:id response adds a "teams" array and changes "plan" from
  string to object
- POST /users now requires an organizationId field
- GET /users/:id/settings is being split into /users/:id/preferences
  and /users/:id/notifications

We have ~200 active API consumers. Help me version this without breaking anyone.
```

### Step 2: Design the Versioning Architecture

URL path versioning wins over header versioning for this use case, and the reasoning matters:

- The mobile app caches aggressively — headers get stripped by CDN caches, but URL paths are always unique
- Partner integrations were built by junior developers who might miss a custom header requirement
- URL versioning is explicit, debuggable (you can see the version in access logs), and CDN-friendly

The architecture separates concerns cleanly: routes define URL structure, controllers contain business logic (written once), and transformers shape the response for each version:

```
src/
  routes/
    v1/users.ts          # v1 URL patterns (unchanged)
    v2/users.ts          # v2 URL patterns (new)
  controllers/
    users.ts             # Shared business logic (version-agnostic)
  transformers/
    v1/user.ts           # Shapes response for v1 clients
    v2/user.ts           # Shapes response for v2 clients
  middleware/
    version.ts           # Version detection and routing
```

The key principle: business logic lives in controllers and is written exactly once. Transformers handle the difference between "plan as a string" (v1) and "plan as an object with tier and limits" (v2). No code duplication — fixing a bug in the user controller fixes it for both API versions simultaneously.

### Step 3: Implement the Versioning Layer

The version middleware extracts the version from the URL path and sets `req.apiVersion` for downstream use. Unsupported versions get a `400` with a list of valid versions.

Response transformers do the actual shape-shifting:

```typescript
// transformers/v1/user.ts — keeps the old shape
export function transformUser(user: UserEntity) {
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    plan: user.subscription.tier,  // Flat string: "pro"
    // No teams array — v1 clients don't expect it
  };
}

// transformers/v2/user.ts — new shape with teams
export function transformUser(user: UserEntity) {
  return {
    id: user.id,
    name: user.name,
    email: user.email,
    plan: {                        // Object with details
      tier: user.subscription.tier,
      limits: user.subscription.limits,
      billing_cycle: user.subscription.billingCycle,
    },
    teams: user.teams.map(t => ({ id: t.id, name: t.name, role: t.role })),
  };
}
```

Every v1 response includes sunset headers so clients know the clock is ticking:

```
Sunset: Sat, 17 Aug 2026 00:00:00 GMT
Deprecation: true
Link: </api/v2/users>; rel="successor-version"
```

Routing is three lines in `app.ts`:

```typescript
app.use('/api/v1', v1Router);
app.use('/api/v2', v2Router);
app.use('/api', v2Router);  // Unversioned defaults to latest
```

### Step 4: Generate Backward Compatibility Tests

The test suite covers 47 cases across three categories:

**v1 backward compatibility (23 tests):** every existing endpoint returns the exact same response shape it always has. `GET /api/v1/users/:id` returns `plan` as a flat string. The `teams` array is absent. `POST /api/v1/users` works without `organizationId`. `GET /api/v1/users/:id/settings` still works (not split). Every v1 response includes the `Sunset` header.

**v2 new behavior (18 tests):** `GET /api/v2/users/:id` returns `plan` as an object with `tier`, `limits`, and `billing_cycle`. The `teams` array is present. `POST /api/v2/users` requires `organizationId` and returns 400 without it. `GET /api/v2/users/:id/settings` returns a `301` redirect to `/preferences`.

**Cross-version consistency (6 tests):** the same user data returns correctly shaped for both versions. A user created via v1 is readable via v2 and vice versa. Requesting `/api/v3/` returns `400` with a list of supported versions.

### Step 5: Write Migration Documentation

The agent generates three documents:

**Migration guide** (`docs/api/migration-v1-to-v2.md`) -- side-by-side response comparisons showing exactly what changed at the field level. Code examples in JavaScript, Python, and cURL for every changed endpoint. A checklist for migrating client code.

**Changelog** (`docs/api/changelog-v2.md`) -- every breaking change with the rationale behind it. Non-breaking additions listed separately so consumers know what is new versus what requires changes.

**Sunset policy** (`docs/api/sunset-policy.md`) -- the timeline: v1 is deprecated now, returns `Sunset` headers immediately, and will be removed in August 2026. Support contact for migration questions. The policy document becomes the reference that customer success shares with partners proactively, instead of the old approach of emailing after the fact.

The documentation is not an afterthought — it is part of the versioning strategy. A well-written migration guide with working code examples reduces the support burden from "help us migrate" tickets to "we migrated, just confirming it works" messages.

## Real-World Example

Kenji ships v2 alongside v1 on a Tuesday. The deploy is anticlimactic — which is exactly the point. Nothing breaks. v1 clients continue working exactly as before, now with sunset headers quietly warning them in every response. The migration guide goes out to partners the same day, and the developer community finds it in the API docs.

Over the next four months, API consumers migrate at their own pace. The v1 usage dashboard (built from access log analysis) shows a steady decline: 100% v1 on day one, 60% after one month, 20% after three months. Kenji's team reaches out directly to the remaining v1 consumers in month four with specific migration help.

The partner who churned after the last breaking change? Their new integration lead finds the migration guide, follows the code examples, and migrates in an afternoon. No broken integration, no angry email, no churn. The mobile app ships a v2 update that coexists with the old version — users on old app versions hit v1, updated users hit v2, and both work perfectly.

By August 2026, v1 traffic is under 1%. The team removes v1 routes, transformers, and tests in a clean 200-line deletion. Zero customer impact.

The versioning infrastructure stays in place for the next breaking change — and this time, the team knows exactly how to handle it. The response transformer pattern, the sunset headers, the migration guide template, and the usage dashboard are all reusable. What took a week of debate and three months of fallout the first time now has a playbook that takes a day to execute.
