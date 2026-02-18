---
title: "Set Up Automated Performance Regression Detection"
slug: set-up-performance-regression-detection
description: "Catch performance regressions in CI before they reach production by benchmarking every PR against baseline metrics."
skills: [cicd-pipeline, api-tester, report-generator]
category: devops
tags: [performance, regression, benchmarking, CI, latency]
---

# Set Up Automated Performance Regression Detection

## The Problem

Last Tuesday, a PR that "just refactored the query builder" made it to production and doubled the p95 latency on your main API endpoint. Nobody noticed until a customer complained 3 hours later. The rollback took another 45 minutes, and the root cause took a day to find — an innocent-looking change added an N+1 query inside a loop.

This keeps happening. Your 15-person engineering team ships 30-40 PRs per week. Each PR passes tests, gets code review, and merges. But nobody checks performance. Load testing happens quarterly at best. By the time regressions are noticed, they've been in production for days and are tangled with other changes. Bisecting through 30 PRs to find which one introduced 200ms of latency is nobody's idea of a productive afternoon.

You need automated performance checks on every PR — not a full load test, but enough to catch the obvious regressions before they merge.

## The Solution

Use **api-tester** to run performance benchmarks against key endpoints, **cicd-pipeline** to integrate checks into your PR workflow, and **report-generator** to surface results as clear PR comments.

## Step-by-Step Walkthrough

### Step 1: Identify Critical Performance Paths

```text
Analyze our API routes and identify the top 10 endpoints by traffic volume
and latency sensitivity. These will be our benchmark targets.
```

Not every endpoint needs benchmarking — only the ones where a regression would actually matter. The top 10 are selected by a combination of traffic volume and business impact:

| Endpoint | Traffic | Current p95 | Why it matters |
|----------|---------|-------------|----------------|
| `GET /api/orders` | 12K req/hr | 340ms | Revenue-critical, most-hit page |
| `POST /api/orders` | 3K req/hr | 280ms | Checkout flow |
| `GET /api/products/search` | 8K req/hr | 520ms | User-facing search |
| `GET /api/dashboard/stats` | 2K req/hr | 890ms | Admin dashboard |
| `POST /api/auth/login` | 1.5K req/hr | 180ms | Auth gate, blocks everything |
| `GET /api/users/:id` | 4K req/hr | 120ms | Profile loads |
| `POST /api/webhooks/stripe` | 500 req/hr | 450ms | Payment processing |
| `GET /api/reports/export` | 200 req/hr | 2.1s | Data export |
| `POST /api/events` | 6K req/hr | 90ms | Analytics ingestion |
| `GET /api/notifications` | 3K req/hr | 210ms | Real-time feeds |

Baselines are recorded from production metrics over the last 7 days (p50, p95, p99). These become the reference numbers every PR is compared against. The 7-day window smooths out day-of-week variation while staying fresh enough to reflect recent legitimate changes.

### Step 2: Create the Benchmark Suite

```text
Build a benchmark configuration that tests these 10 endpoints with realistic
payloads. Each test should run 100 requests and measure p50, p95, and p99 latency.
```

The benchmark config at `benchmarks/performance.config.json` defines 10 scenarios with realistic payloads — actual order objects with line items, real search queries that exercise the full-text index, valid auth credentials that trigger the complete authentication flow. Fake payloads miss the very code paths that cause regressions.

Each scenario runs a warmup phase (10 requests to eliminate cold-start noise from JIT compilation and connection pool initialization) followed by the actual benchmark: 100 requests at 10 concurrent connections, measuring p50, p95, and p99 latency plus throughput.

Seed data lives in `benchmarks/fixtures/` so every run operates on the same dataset. Total runtime: about 45 seconds per full run. Fast enough to run on every PR without adding meaningful wait time to the review cycle.

### Step 3: Set Up the CI Pipeline

```text
Add a GitHub Actions workflow that runs benchmarks on every PR. Compare results
against the main branch baseline. Fail the check if any endpoint regresses
more than 20%.
```

The workflow at `.github/workflows/performance.yml` triggers on PRs that touch `src/` or `package.json` — no point benchmarking a README change or a CI config tweak. The steps:

1. Start services via `docker compose up -d` (Postgres, Redis, API)
2. Seed benchmark data with `npm run bench:seed`
3. Check out the main branch, run benchmarks: `npm run bench > baseline.json`
4. Check out the PR branch, run benchmarks: `npm run bench > current.json`
5. Compare with `node benchmarks/compare.js baseline.json current.json`

Both runs use identical infrastructure, identical data, identical concurrency. The only variable is the code.

Thresholds are set at two levels:
- **Warning** (yellow check): any endpoint p95 regressed more than 10%
- **Failure** (red check): any endpoint p95 regressed more than 20%, or any p99 exceeded 3 seconds

A warning doesn't block the merge — it just makes the engineer and reviewer aware. A failure blocks the merge until someone investigates. The whole workflow runs in about 3 minutes: Docker startup, seed, 45-second benchmark run for each branch, comparison.

### Step 4: Generate the Comparison Report

```text
Format the benchmark comparison as a clear PR comment showing before/after
for each endpoint.
```

Results are posted as a PR comment with a comparison table that anyone can read at a glance:

| Endpoint | Baseline p95 | PR p95 | Change | Status |
|----------|-------------|--------|--------|--------|
| GET /orders | 342ms | 348ms | +1.8% | Pass |
| POST /orders | 278ms | 412ms | +48.2% | **REGRESSION** |
| GET /products/search | 518ms | 502ms | -3.1% | Pass (improved) |
| GET /dashboard/stats | 891ms | 884ms | -0.8% | Pass |
| POST /auth/login | 182ms | 179ms | -1.6% | Pass |

When a regression is detected, the comment goes beyond just flagging the number. It identifies which endpoint regressed, by how much, and suggests likely causes based on the changed files: "Likely cause: new middleware added in `src/orders/create.ts`. Check for N+1 queries or unnecessary async operations." The engineer sees the problem before a reviewer has to catch it, and gets a starting point for the investigation.

### Step 5: Track Performance Trends Over Time

```text
Store benchmark results from each merged PR. Generate a weekly trend report
showing performance trajectory per endpoint.
```

Every merged PR's benchmark results get stored in `benchmarks/history/` as timestamped JSON files. A weekly cron job aggregates them into trajectory reports:

| Endpoint | Week 1 | Week 2 | Week 3 | Week 4 | Trend |
|----------|--------|--------|--------|--------|-------|
| GET /orders | 340ms | 342ms | 338ms | 348ms | Stable |
| GET /products/search | 580ms | 540ms | 520ms | 502ms | Improving |
| GET /dashboard/stats | 650ms | 780ms | 850ms | 884ms | **Degrading** |

This catches something the per-PR threshold checks completely miss: cumulative drift. The dashboard stats endpoint has regressed 36% over 4 weeks across 8 small PRs. Each PR added just 3-5% latency — well under the 20% failure threshold. But the cumulative effect is significant, and without trend tracking, nobody would have noticed until a user complained that the dashboard takes forever to load.

When cumulative drift is detected, an issue is automatically opened: "Performance: /dashboard/stats cumulative regression — 36% over 4 weeks." The trend data tells the team exactly when the degradation started and which PRs contributed.

## Real-World Example

Amir, a senior engineer at a 15-person e-commerce SaaS, was tired of being the human performance detector. He'd notice slow endpoints in production monitoring, bisect through recent PRs, and find the culprit — usually a well-meaning change with an unexpected performance impact. This happened 2-3 times per month, and each incident cost hours of investigation time.

He set up the workflow on a Friday. Benchmarks for the 10 highest-traffic endpoints, a 3-minute performance check on every PR. In the first week, it caught 2 regressions before merge — one was an N+1 query in the orders endpoint (+48% latency), the other was an unnecessary JSON serialization in the auth flow. Both would have made it to production under the old process.

The weekly trend report revealed something nobody had noticed: the dashboard stats endpoint had been slowly degrading over 4 weeks across 8 small PRs, each adding 3-5% latency. The team consolidated 3 database queries into 1 and brought it back to baseline. Monthly performance incidents dropped from 2-3 to zero over the next quarter. Amir stopped being the human performance detector — the CI pipeline took over the job.
