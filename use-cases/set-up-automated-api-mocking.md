---
title: "Set Up Automated API Mocking for Frontend Development with AI"
slug: set-up-automated-api-mocking
description: "Use AI to generate mock API servers from OpenAPI specs, seed them with realistic data, and keep mocks in sync with backend changes."
skills: [api-tester, coding-agent, test-generator]
category: development
tags: [api-mocking, frontend, openapi, development-workflow, testing]
---

# Set Up Automated API Mocking for Frontend Development with AI

## The Problem

Priya leads a frontend team of three at a 20-person SaaS startup. They depend on a backend API that's half-built. Endpoints change weekly, new fields appear without warning, and the backend team is in a different timezone -- by the time the frontend team starts work in the morning, the backend team is wrapping up their day.

The result: two hours every morning spent figuring out which endpoints work, which are broken, and what the response shapes look like today. Developers hardcode fake data directly in their components -- `const user = { name: "Test User", email: "test@test.com" }` -- which renders perfectly in development and breaks the moment it meets real API data. Integration bugs pile up at the end of every sprint because the frontend was built against imaginary data, not the actual contract. Last sprint: 14 integration bugs at merge time. The sprint before that: 11. The trend is getting worse, not better.

## The Solution

Use the **api-tester** skill to validate the current OpenAPI spec against the live backend and identify discrepancies. Have the **coding-agent** generate a mock server from the spec with realistic seed data. Use the **test-generator** to create contract tests that alert when the backend spec changes, keeping mocks perpetually in sync.

## Step-by-Step Walkthrough

### Step 1: Validate the OpenAPI Spec Against Reality

The OpenAPI spec is supposed to be the single source of truth. In practice, it drifts. Fields get added to responses without updating the spec, endpoints that aren't built yet still appear as "available," and the spec occasionally contradicts itself.

```text
Download the OpenAPI spec from https://api.internal.dev/docs/openapi.json. Validate it for completeness -- flag any endpoints missing response schemas, any fields without types, and any mismatches between the spec and actual API responses by hitting each GET endpoint once.
```

The validation hits all 34 endpoints and finds the drift:

| Endpoint | Issue |
|---|---|
| `GET /api/projects` | Undocumented field: `archived_at` (string, nullable) |
| `GET /api/users/:id` | Undocumented field: `avatar_url` (string) |
| `GET /api/tasks` | Undocumented field: `priority` (integer) |
| `POST /api/tasks` | Response missing `created_by` field that spec promises |
| `GET /api/reports/burndown` | Returns 501 -- not implemented yet |
| `POST /api/reports/export` | Returns 501 -- not implemented yet |

28 endpoints match their spec. 4 have undocumented fields (the backend added them, the spec didn't follow). 2 are stubs that return 501. This discrepancy report alone saves hours of debugging -- now the frontend team knows exactly which fields exist in reality versus on paper.

### Step 2: Generate a Mock Server with Realistic Data

Hardcoded fake data in components is a landmine. A proper mock server serves the same shapes as the real API, with realistic enough data to expose edge cases (long names, empty arrays, null fields, unicode characters).

```text
Generate a mock API server using MSW (Mock Service Worker) that serves all 34 endpoints from the OpenAPI spec. For each endpoint, generate 20 realistic seed records. Use proper names, dates, UUIDs, and domain-appropriate values (project names, task descriptions). Handle pagination, filtering, and error responses.
```

The mock server structure:

```
mocks/
  handlers/
    projects.ts    -- 6 handlers (CRUD + list + archive)
    users.ts       -- 4 handlers (CRUD + list)
    tasks.ts       -- 8 handlers (CRUD + list + assign + status transitions)
    reports.ts     -- 2 handlers (stub 501 responses, matching reality)
  seed/
    projects.json  -- 20 projects: "Q1 Platform Redesign", "Mobile App v3.0", ...
    users.json     -- 20 users with realistic names, emails, roles, avatar URLs
    tasks.json     -- 60 tasks linked to projects and users with varied statuses
  server.ts        -- MSW setup with all handlers registered
  browser.ts       -- Browser worker for Storybook integration
```

The seed data isn't random gibberish -- project names sound like real projects, task descriptions contain actual sentences, dates span a realistic range, and some fields are intentionally null or empty to test edge cases. One user has a 47-character name to catch truncation bugs. One project has zero tasks to test empty states. This is the kind of testing surface that hardcoded `"Test User"` data never provides.

### Step 3: Wire the Mock Server into Development

The mock server needs to activate seamlessly -- no code changes to switch between mock and real API, and it needs to work in both the dev server and Storybook.

```text
Configure our Next.js app to use the MSW mock server in development and Storybook. The mock server should activate automatically when NEXT_PUBLIC_API_MOCKING=true. Add a toggle in the browser dev tools to switch between mock and real API.
```

With `NEXT_PUBLIC_API_MOCKING=true` in the `.env.development` file, MSW intercepts all fetch requests and returns mock data. In Storybook, the browser worker handles the same interception. The dev tools toggle lets a developer flip between mock and real API without restarting the server -- useful when they need to verify something against the actual backend.

The frontend team stops spending two hours every morning figuring out what works. The mock server always works, and it always returns the right shapes.

### Step 4: Generate Contract Tests

Mocks drift from reality the same way specs do -- unless something enforces the contract. Contract tests compare mock responses against the OpenAPI spec and fail the moment they disagree.

```text
Create contract tests that compare the mock server responses against the OpenAPI spec. If the backend team updates the spec, these tests should fail immediately and show exactly which fields changed. Run them in CI on every PR.
```

Thirty-four contract tests in `tests/contracts/`, one per endpoint:

```typescript
// tests/contracts/projects.test.ts
test('GET /api/projects response matches schema', async () => {
  const response = await mockServer.get('/api/projects');
  // Validates: all 12 fields present, correct types, no extra fields
  // Fails with: "Field 'archived_at' in response but not in schema"
  expect(response).toMatchOpenAPISchema('GET /api/projects');
});
```

CI integration: the GitHub Actions workflow downloads the latest OpenAPI spec from the backend team's repo, runs all 34 contract tests against the mock handlers, and fails the PR if any schema mismatch is detected. When the backend adds a new field, the test says exactly which field changed and in which endpoint -- the frontend developer updates the mock in minutes instead of discovering the mismatch at integration time.

### Step 5: Auto-Update Mocks When the Spec Changes

The final piece: when the backend team publishes a spec update, the mocks should update themselves for simple changes (added fields, type changes) and flag complex changes (removed fields, renamed endpoints) for manual review.

```text
Write a script that diffs the current OpenAPI spec against the last known version. When fields are added, auto-generate new seed data and update handlers. When fields are removed, flag them for manual review. Run this as a daily CI job.
```

A daily job pulls the latest spec, compares it to the stored version, and handles the diff:

- **Added fields**: Automatically generates appropriate seed data based on the field type and name (a field called `avatar_url` gets realistic image URLs, not random strings) and updates the handler to include it.
- **Removed fields**: Flags for manual review with a Slack notification. Removing a field might mean the frontend needs to update a component, and that shouldn't happen silently.
- **Type changes**: Flags for review -- a field changing from `string` to `number` probably means a breaking change.

The spec version gets committed after each sync, so the diff always shows incremental changes rather than accumulating drift.

## Real-World Example

Priya's team notices the difference within the first week. Monday morning: instead of spending two hours probing the API, everyone starts building immediately against the mock server. A developer finishes a project list component on Tuesday, confident the data shape is correct because the mock mirrors the validated spec.

Thursday, the daily spec sync catches a change: the backend team added a `priority` field to the tasks endpoint (one of the undocumented fields from the initial audit, now formalized). The mock auto-updates with seed data, and the contract test for the frontend's task handler fails -- showing exactly which component needs to handle the new field.

After one month, sprint integration bugs drop from 14 to 2. The two remaining bugs are business logic issues, not data shape mismatches -- the kind of bugs that actually require human judgment to resolve. The team ships features three days faster per sprint because they stopped waiting for backend endpoints to stabilize. The mock server gave them stability to build against, and the contract tests gave them confidence that stability reflects reality.
