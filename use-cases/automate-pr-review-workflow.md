---
title: "Automate PR Reviews for Style, Tests, Security, and Performance in One Pass"
slug: automate-pr-review-workflow
description: "Run a comprehensive AI-powered PR review covering code style, test coverage, security vulnerabilities, and performance issues in a single pass."
skills: [code-reviewer, security-audit, performance-reviewer, test-generator]
category: development
tags: [code-review, pull-request, security, performance, testing]
---

# Automate PR Reviews for Style, Tests, Security, and Performance in One Pass

## The Problem

Code reviews are the biggest bottleneck in most development teams. A thorough review requires checking style consistency, test coverage, security vulnerabilities, and performance implications — but most reviewers only catch one or two of these. Senior engineers spend 5-10 hours per week reviewing PRs, and things still slip through. The result: slow merge cycles, missed security issues, and performance regressions that surface in production.

The math is brutal. A 6-person team opening 30 PRs per week needs roughly 15 hours of senior engineer time just for reviews. And even that isn't enough — the security-focused engineer catches injection bugs but misses the N+1 query, while the performance-minded engineer catches the N+1 but doesn't notice the missing authorization check. No single reviewer holds all four lenses at once. So PRs get approved with blind spots, and the team discovers problems in staging — or worse, in production.

## The Solution

Using the **code-reviewer**, **security-audit**, **performance-reviewer**, and **test-generator** skills, the agent runs four review passes on every PR — code quality, security, performance, and test coverage — then produces a single consolidated report. Review depth that would take a senior engineer an hour gets compressed into minutes, and nothing falls through the cracks because each dimension has its own dedicated pass.

## Step-by-Step Walkthrough

### Step 1: Kick Off a Full Review

Point the agent at a PR branch:

```text
Review the PR on branch feature/user-permissions against main. Check everything: style, security, performance, and test coverage. Give me one consolidated report.
```

### Step 2: Four-Dimensional Analysis of the Diff

The review comes back organized by dimension. Each pass runs independently, so a security finding doesn't get buried in a style nit, and a missing test doesn't get lost in a performance warning. Here's what the `feature/user-permissions` branch (14 files changed, +487 -92) reveals:

**Code Quality** (via code-reviewer):

- `src/middleware/auth.ts:23` — Nested ternary reduces readability. Should be extracted to a named function like `resolvePermissionLevel(role, resource)`.
- `src/models/Permission.ts:45-67` — Switch statement with 12 cases and duplicated logic. A permission map (`Record<Role, Permission[]>`) would cut this to 12 lines and make it trivial to add new roles.
- Naming conventions consistent across the PR. No unused imports detected.

**Security** (via security-audit):

- **CRITICAL** `src/api/users.ts:34` — User ID taken from request body without verifying it matches the authenticated user. This allows horizontal privilege escalation: anyone with a valid token can `PUT /api/users/other-user-id` and modify another account.

```typescript
// Vulnerable — user controls which account gets modified
const userId = req.body.userId;
await updateUser(userId, req.body.changes);

// Fixed — user ID comes from the verified auth token
const userId = req.auth.userId;
await updateUser(userId, req.body.changes);
```

- **WARNING** `src/middleware/auth.ts:15` — Permission check uses string comparison (`role === "admin"`) instead of an enum. A typo like `"admnin"` would silently fail open — the check passes for everyone because the condition never matches.

This is the kind of vulnerability that's invisible during a normal code review. The logic looks right at a glance — there's an `if` check, the variable names make sense. But the data flow is wrong: the user controls the ID being checked. Without a dedicated security pass, this would ship.

**Performance** (via performance-reviewer):

- **WARNING** `src/api/users.ts:52` — Loading all permissions for a user with a query per role (N+1). With 5 roles assigned, that's 6 queries per request.

```typescript
// N+1 — one query per role
for (const role of user.roles) {
  const perms = await db.permissions.findByRole(role.id);
  // ...
}

// Fixed — single query
const perms = await db.permissions.findByRoles(user.roles.map(r => r.id));
```

At 100 requests per second, that's 600 database queries per second where 100 would suffice. Not a problem at current scale, but it'll become one.

- **INFO** `src/api/teams.ts:78` — Sequential awaits for fetching team members and permissions. `Promise.all()` would parallelize them and save roughly 200ms per request.

**Test Coverage** (via test-generator):

- **CRITICAL** No tests for the new permission middleware. This is the most critical code in the PR — authorization logic without tests is a liability. Generated: `tests/middleware/auth.test.ts` with 8 test cases covering: admin access, member access, unauthenticated requests, expired tokens, invalid roles, resource-level permissions, cross-tenant access, and role inheritance.
- **WARNING** `src/api/users.ts` — Existing tests don't cover the new permission check on the update endpoint. Added 3 test cases to `tests/api/users.test.ts`.

**Summary: 1 critical security issue, 1 critical test gap, 3 warnings, 2 info.**

The two critical findings are the key takeaway. The privilege escalation would have let any authenticated user modify any other user's account — a vulnerability that could lead to account takeovers, data theft, and a very bad disclosure email to customers. The missing tests mean that even after fixing the security issue, there's no guarantee a future PR won't reintroduce it. Both need to be resolved before merge.

### Step 3: Fix Critical Issues and Re-Review

After addressing the privilege escalation and adding tests:

```text
I fixed the privilege escalation and added the permission middleware tests. Can you re-review just the changed files?
```

The re-review of 3 changed files comes back clean on the critical items:

- **Security** — Privilege escalation fixed. `req.auth.userId` now used correctly. The handler rejects requests where the path parameter doesn't match the authenticated user.
- **Tests** — Permission middleware has 8 tests, all passing. Coverage: 94%. The remaining 6% is error handling for malformed JWT payloads — worth covering but not blocking.
- **Remaining** — The N+1 query on user permissions is still there. It's a warning, not a blocker at current scale (under 1,000 users). Created an issue suggestion for tracking it as a follow-up.

**Verdict: Safe to merge.** The critical security and test coverage issues are resolved. The remaining items are improvements, not blockers.

### Step 4: Get a Merge-Ready Summary

The final step is producing something the team can read at a glance. Nobody wants to re-read the full analysis — they want the verdict, what was fixed, and what's left for follow-up.

```text
Write a review summary I can post on the PR.
```

The summary is ready to paste directly into the PR comment:

**Status: Approved**

**What this PR does:** Adds role-based permission system with middleware for route-level authorization. Six new middleware functions, updated user and team API endpoints, and a permissions model.

**Review findings (resolved):**
- Fixed horizontal privilege escalation in user update endpoint — user ID now sourced from auth token, not request body
- Added 11 tests for permission middleware and user API (94% coverage)

**Follow-up items:**
- Optimize permission loading query (N+1, low priority at current scale)
- Migrate role strings to TypeScript enum for type safety

Reviewed: code quality, security, performance, test coverage.

The entire cycle — initial review, fix, re-review, summary — takes about 20 minutes of developer time. A human-only review cycle for a 14-file PR with security implications would typically take 2-3 rounds over 2-4 days.

## Real-World Example

Priya leads a 6-person engineering team at a 30-person B2B SaaS startup. Their PR review process averages 2 days from open to merge because the two senior engineers are the bottleneck — they're the only ones who reliably catch security and performance issues. Every PR sits in a queue, and the senior engineers context-switch between feature work and reviews all day. Junior developers wait, lose context, and pick up other work in the meantime, which means they need to re-load context when the review finally arrives.

She configures the AI agent to run on every PR opened against `main`, reviewing across all four dimensions automatically. The first real test comes when a junior developer opens a PR adding a new API endpoint for exporting user data. Within 3 minutes, the agent flags an SQL injection vulnerability in the query builder, a missing rate limit on the export endpoint (which could be used to scrape the entire user database), and generates 6 missing test cases. The junior developer fixes everything before any human reviewer sees the PR — the PR that reaches the senior engineer is already clean.

Over the first month, the numbers tell the story. Average time-to-merge drops from 2 days to 6 hours. Security issues caught before human review jump from 30% to 95%. The two senior engineers reclaim roughly 8 hours per week that was going to line-by-line reviews. They still review every PR — but now they spend their time on architecture and design decisions instead of hunting for SQL injections and missing null checks. The agent handles the mechanical checks; the humans handle the judgment calls. The team ships faster, and what they ship is more secure.
