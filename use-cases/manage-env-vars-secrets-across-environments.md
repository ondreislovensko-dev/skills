---
title: "Manage Environment Variables and Secrets Across Environments with AI"
slug: manage-env-vars-secrets-across-environments
description: "Audit, sync, and secure environment variables across dev, staging, and production using an AI agent."
skills: [env-manager, doppler, security-audit]
category: devops
tags: [environment-variables, secrets, devops, security, configuration]
---

# Manage Environment Variables and Secrets Across Environments with AI

## The Problem

Environment variable management is a silent source of outages. A missing `STRIPE_WEBHOOK_SECRET` in production means payments silently fail -- no crash, no error in the logs, just webhooks that never process. A shared `JWT_SECRET` between staging and production means a staging token works against live data, which is how a QA engineer accidentally deleted 200 production records last quarter.

Most teams manage env vars through a mix of `.env` files committed to repo history (even if deleted later, they're in git forever), CI/CD settings scattered across GitHub Actions and Vercel dashboards, and a Notion page titled "Secrets" that's six months out of date. There's no single view of what's set where. New developers spend their first day chasing down 15 different secrets just to run the app locally, asking in Slack channels where each one comes from.

## The Solution

Using the **env-manager** skill to scan the codebase for every environment variable reference, compare them across environments, and flag missing, stale, or insecure configurations, combined with **doppler** for secrets management and **security-audit** for detecting exposed credentials, the agent builds a complete picture of configuration health -- and fixes the gaps.

The approach is systematic: first audit what exists (code references vs documentation vs what's actually set), then compare across environments (dev vs staging vs production), then fix the issues in priority order (security first, then functionality, then cleanup).

## Step-by-Step Walkthrough

### Step 1: Audit the Current State

Start with a full scan:

```text
Audit all environment variables in this project. Check what's referenced in
code vs what's documented in .env.example vs what's actually set in our
Vercel project.
```

The scan covers 142 source files, looking for `process.env.`, `import.meta.env.`, Zod schemas, and configuration files. It finds 38 unique environment variables referenced in the codebase.

The gap between documentation and reality is immediately visible: 31 of 38 variables are documented in `.env.example` (82%), 7 are referenced in code but completely undocumented (a new developer would never know they exist), and 4 are documented in `.env.example` but no longer referenced anywhere in the code -- leftovers from features removed months ago that nobody cleaned up.

Breakdown by category:

| Category | Count | Variables |
|----------|-------|-----------|
| Database | 3 | `DATABASE_URL`, `REDIS_URL`, `MONGODB_URI` |
| Auth | 5 | `JWT_SECRET`, `NEXTAUTH_SECRET`, `GOOGLE_CLIENT_ID`, ... |
| Payments | 4 | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, ... |
| Email | 3 | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS` |
| Third-party | 8 | `OPENAI_API_KEY`, `SENTRY_DSN`, `SEGMENT_WRITE_KEY`, ... |
| Feature flags | 6 | `FF_NEW_DASHBOARD`, `FF_BILLING_V2`, ... |
| App config | 9 | `NEXT_PUBLIC_API_URL`, `RATE_LIMIT_MAX`, ... |

Three variables are critical risks -- they're used in code with no validation and no default value:

- **`STRIPE_WEBHOOK_SECRET`** (`src/api/webhooks.ts:8`) -- app crashes if missing
- **`OPENAI_API_KEY`** (`src/lib/ai.ts:3`) -- API calls fail with a cryptic error message
- **`REDIS_URL`** (`src/lib/cache.ts:5`) -- silently falls back to localhost, which works in dev and fails in production with no useful error

### Step 2: Compare Across Environments

```text
Now compare what's set in development, staging (Vercel preview), and
production (Vercel production).
```

The cross-environment comparison reveals two categories of problems:

**Missing in production (2):**
- `SENTRY_DSN` -- no error tracking in prod, meaning bugs go unnoticed
- `FF_BILLING_V2` -- feature flag defaults to off, so billing v2 will never activate

**Security concerns (3):**
- `JWT_SECRET` is identical in staging and production -- a token minted against staging data works against the production database
- `NEXT_PUBLIC_SENTRY_DSN` contains a project auth token exposed to the client bundle
- `DATABASE_URL` in staging uses a production-like connection string that warrants verification

The remaining 28 variables correctly differ across environments. Five variables are staging/dev-only debug flags, which is expected.

This kind of cross-environment comparison is nearly impossible to do manually. You'd need to check the Vercel dashboard for each environment, diff the results against `.env.example`, then cross-reference with what the code actually uses. It takes 20 minutes of clicking around dashboards, and nobody does it regularly -- which is how `SENTRY_DSN` was missing for 3 months without anyone noticing.

### Step 3: Apply Fixes Safely

```text
Fix the critical issues. Generate new secrets where needed and set them
in Vercel.
```

The rotation plan addresses each issue in priority order:

**1. JWT_SECRET for production** -- generate a new value with `openssl rand -base64 32`, set via `vercel env add JWT_SECRET production`. This is the most disruptive fix: every active user session will invalidate because existing JWTs were signed with the old secret. The agent recommends deploying during a low-traffic window (Sunday 2-4 AM based on the app's analytics) and preparing a "please sign in again" toast message for the frontend.

**2. SENTRY_DSN for production** -- retrieved from Sentry project settings, set via `vercel env add SENTRY_DSN production`. Immediate effect, no user impact. After this, production errors finally show up in the dashboard instead of disappearing into the void.

**3. FF_BILLING_V2 for production** -- set to `"true"` via `vercel env add FF_BILLING_V2 production`. Activates the billing v2 feature that's been waiting on this flag for two sprints. The feature was "shipped" three weeks ago but never actually turned on in production because nobody remembered to set this variable.

**4. Startup validation** -- this is the most important long-term fix. A new file at `src/lib/env.ts` uses Zod to validate every required environment variable at boot time:

```typescript
// src/lib/env.ts
import { z } from 'zod';

const envSchema = z.object({
  DATABASE_URL: z.string().url(),
  REDIS_URL: z.string().url(),
  JWT_SECRET: z.string().min(32),
  STRIPE_SECRET_KEY: z.string().startsWith('sk_'),
  STRIPE_WEBHOOK_SECRET: z.string().startsWith('whsec_'),
  OPENAI_API_KEY: z.string().startsWith('sk-'),
  SENTRY_DSN: z.string().url().optional(),
  // ... all 38 variables with appropriate validators
});

export const env = envSchema.parse(process.env);
```

The app now fails fast with a clear error listing every missing variable, instead of crashing at runtime when a specific var is first accessed. No more "it works locally but breaks in staging because someone forgot to set OPENAI_API_KEY."

## Real-World Example

Dev, a platform engineer at a 40-person fintech startup, joins during a period of rapid growth. The team has gone from 3 to 12 developers in six months, and onboarding takes two days because nobody knows which of the 45 environment variables are actually needed or where to get them.

He asks the agent to audit the entire configuration surface -- code references, `.env.example`, Vercel settings, and GitHub Actions secrets. The agent discovers 7 undocumented variables, 5 stale ones left over from removed features, and 2 secrets that are identical across staging and production.

Using the audit report, Dev updates `.env.example` with a description comment above every variable explaining what it does, what format it expects, and where to get the value. The stale variables get removed. The Zod validation schema goes into `src/lib/env.ts` so the app fails fast with a clear error on startup instead of crashing mysteriously at runtime.

The agent generates a secure onboarding script (`scripts/setup-env.sh`) that creates a local `.env` from `.env.example`, auto-populates non-secret defaults (like `NEXT_PUBLIC_API_URL=http://localhost:3000`), and interactively prompts for each secret with instructions on where to find the value:

```bash
$ ./scripts/setup-env.sh
Setting up local environment...
[auto] NEXT_PUBLIC_API_URL=http://localhost:3000
[auto] RATE_LIMIT_MAX=100
[prompt] STRIPE_SECRET_KEY: Get from https://dashboard.stripe.com/test/apikeys
  > sk_test_...
[prompt] OPENAI_API_KEY: Get from https://platform.openai.com/api-keys
  > sk-...
Local .env created with 38 variables. Run 'npm run dev' to start.
```

New developer onboarding drops from 2 days to 45 minutes. The Zod validation schema catches missing variables at startup instead of at runtime -- the next production deploy with a missing env var fails immediately during the health check with a clear error listing exactly what's missing, instead of crashing 3 hours later when a user triggers the payment webhook for the first time.

Three months in, the team runs the env audit as part of every sprint retrospective. It takes 30 seconds and has caught configuration drift twice -- both times before it reached production. The Zod validation schema has become the single source of truth for what the application needs to run, and new developers treat it as the first file to read when onboarding.

The biggest win is invisible: the team stopped having production incidents caused by configuration errors. Before the audit, these happened roughly once a month -- a missing API key here, a staging URL accidentally deployed to production there. After: zero in three months. The validation catches every missing or malformed variable at deploy time, not at 2 AM when a customer hits the one code path that references the unset variable.

The onboarding script becomes a model for other teams in the company. Two other projects adopt the same pattern: Zod validation schema plus an interactive setup script plus a CI check that runs the audit on every PR. Configuration management goes from a recurring source of incidents to a solved problem across the engineering organization.
