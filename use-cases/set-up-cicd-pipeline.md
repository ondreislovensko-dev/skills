---
title: "Set Up a Production-Ready CI/CD Pipeline with AI"
slug: set-up-cicd-pipeline
description: "Build a complete CI/CD pipeline with automated testing, Docker optimization, and security scanning gates for production deployments."
skills: [cicd-pipeline, docker-helper, test-generator, security-audit]
category: devops
tags: [cicd, docker, testing, security, deployment]
---

# Set Up a Production-Ready CI/CD Pipeline with AI

## The Problem

Eight developers deploy by SSH-ing into production, running `git pull`, and restarting PM2. No automated tests. No staging environment. No rollback plan. The Docker image is 1.4 GB and takes 8 minutes to build. Last Friday, a broken migration took the API down for 45 minutes before anyone noticed -- on a Friday afternoon, when half the team had already signed off.

Setting up CI/CD properly means coordinating tests, container optimization, security scanning, and deployment. Each one takes a day to configure, and they all need to work together. Nobody wants to spend a week on infrastructure plumbing, so the `git pull` workflow persists.

## The Solution

Four skills build a production-ready pipeline in an afternoon. **test-generator** creates integration tests so the pipeline gates on something meaningful. **docker-helper** cuts the image from 1.4 GB to 156 MB. **cicd-pipeline** assembles the GitHub Actions workflow with staging and production stages. **security-audit** adds vulnerability scanning as a required gate.

## Step-by-Step Walkthrough

### Step 1: Generate Tests Worth Gating On

A pipeline without tests is just automated deployment of broken code. First, the codebase needs coverage:

```text
Generate integration tests for the core API: user management, billing, and webhook processing.
```

Three test suites come out:

| Suite | Tests | What It Covers |
|-------|-------|---------------|
| `tests/integration/users.test.js` | 16 | CRUD, validation, pagination |
| `tests/integration/billing.test.js` | 14 | Subscriptions, invoices, retries |
| `tests/integration/webhooks.test.js` | 11 | Signatures, idempotency, dead letters |

41 tests total, all passing, 64% coverage, 12-second run time. Not exhaustive, but enough to catch the kind of regressions that cause Friday afternoon outages.

### Step 2: Shrink the Docker Image

The 1.4 GB image is a problem for two reasons: build times are painful, and the attack surface is enormous (every unnecessary package is a potential CVE). Time to fix both:

```text
Optimize our Dockerfile. Currently 1.4GB, 8 minutes to build. Needs smaller images, faster builds, security hardening.
```

The optimized Dockerfile applies seven changes:

| Change | Impact |
|--------|--------|
| Multi-stage build (compile stage, runtime stage) | Strips dev dependencies and build tools |
| `node:20` to `node:20-alpine` | Smaller base image |
| `.dockerignore` added | Excludes tests, docs, `.git` |
| Dependency layer caching (`package*.json` first, then `npm ci --production`) | Rebuilds only when deps change |
| Non-root user with minimal permissions | Security hardening |
| `HEALTHCHECK` every 30s | Container orchestrator can detect failures |
| Base image pinned to SHA digest | Reproducible builds |

**Result:** 1.4 GB down to 156 MB (89% reduction). Build time from 8:12 to 1:43 (79% faster).

### Step 3: Assemble the Pipeline

Now the pieces come together into a single GitHub Actions workflow:

```text
Create a GitHub Actions pipeline: lint, test, build Docker image, deploy to staging on merge, production on release tag. Cache node_modules and Docker layers.
```

The pipeline runs in five stages:

```yaml
# .github/workflows/ci.yml (simplified structure)

# 1. LINT (30s) — ESLint + Prettier
# 2. TEST (45s) — 41 tests with PostgreSQL service container
#    Gate: fails below 60% coverage
# 3. BUILD (1:43) — Multi-stage Docker, layer cache, push to GHCR
# 4. STAGING — On merge to main: deploy + smoke tests
# 5. PRODUCTION — On v*.*.* tags: blue-green deploy with health checks
#    Auto-rollback if health check fails within 5 minutes
```

Test coverage gets posted as a PR comment so reviewers can see it without leaving GitHub. The staging deploy runs 5 smoke tests against the live environment. The production deploy uses blue-green with a 5-minute health check window -- if the new version fails health checks, traffic routes back to the old version automatically.

Total time from commit to staging: about 4 minutes.

### Step 4: Add Security Gates

The pipeline should block vulnerabilities before they reach production:

```text
Add security scanning to the pipeline. SAST, dependency audit, Docker image scan, secret detection. Block on critical findings.
```

Four security gates slot in between the TEST and BUILD stages:

- **SAST** -- Semgrep with Node.js + Express rulesets
- **Dependency scan** -- `npm audit` plus Snyk for transitive CVEs
- **Secret detection** -- Gitleaks on PR diff
- **Container scan** (post-build) -- Trivy scans the Docker image, fails on CRITICAL

All findings post as inline PR review comments, so developers see the exact line with the issue.

The initial scan immediately catches two problems:

```
  axios 0.21.1 — SSRF vulnerability (CVE-2023-45857) -> updated to 1.6.2
  Missing X-Content-Type-Options header -> added helmet middleware
```

Both fixes take 5 minutes. Without the gate, these would have stayed in production indefinitely.

### Step 5: Validate End-to-End

One full pipeline run confirms everything works together:

```text
Run the full pipeline end-to-end. Deploy to staging and verify everything works together.
```

| Stage | Result | Time |
|-------|--------|------|
| Lint | 0 issues | 32s |
| Tests | 41/41 passing, 64% coverage | 45s |
| Dependency scan | 0 vulnerabilities | 12s |
| SAST | 0 findings | 18s |
| Secret scan | 0 leaks | 8s |
| Docker build | 156 MB, cached | 1:43 |
| Container scan | 0 critical | 22s |
| Staging deploy | Health check passing | 38s |
| Smoke tests | 5/5 passing | 15s |

**Total: 4 minutes 18 seconds from commit to staging.** The pipeline is ready.

## Real-World Example

The first week live tells the story. Security gates block 2 PRs with dependency vulnerabilities -- both get fixed before merge. The test gate catches a regression in the billing retry logic that would have caused double-charges. All three catches happen before production, during normal PR review.

Deployment goes from 25 minutes of manual SSH work to 4 minutes of automated pipeline. The Docker image is 90% smaller. The team has security scanning they never had before. And most importantly, the Friday afternoon outage scenario is gone -- broken code cannot reach production without passing 41 tests, 4 security scans, and a health check. Zero outages in the following 3 months.
