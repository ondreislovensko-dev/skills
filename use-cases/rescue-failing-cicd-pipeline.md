---
title: "Rescue a Failing CI/CD Pipeline and Cut Build Times"
slug: rescue-failing-cicd-pipeline
description: "Diagnose flaky tests, optimize slow builds, and fix unreliable CI/CD pipelines that waste engineering hours."
skills: [cicd-pipeline, test-generator, docker-helper]
category: devops
tags: [cicd, pipeline, optimization, flaky-tests, build-time]
---

# Rescue a Failing CI/CD Pipeline and Cut Build Times

## The Problem

Monday standup: "CI is red again." Three engineers nod -- they've already re-run builds twice hoping they'll pass. The pipeline takes 43 minutes and fails 28% of the time from flaky tests. Everyone knows the ritual: push, get coffee, fail, re-trigger, lunch, merge if green.

The numbers are brutal. Eight engineers, 6 PRs per day. Each failed run wastes 43 minutes of pipeline time plus 15 minutes of context-switching while the developer figures out whether the failure is real or random. That's 22 engineering hours per week -- nearly 3 full-time equivalents consumed by a broken pipeline. There are 14 tests that fail intermittently from timing issues, shared state, or race conditions. Combined flake probability: 72% chance at least one fails on any given run. A coin flip would be more reliable.

Slow builds compound the problem. Docker builds that don't cache. Serial tests that could parallelize. Dependencies installed from scratch every single run. A 43-minute feedback loop means bigger PRs, harder reviews, more conflicts. CI costs have crept from $200 to $840 per month from re-runs alone. The pipeline was supposed to give the team confidence. Instead, it's the team's biggest source of frustration.

## The Solution

Combine **cicd-pipeline** for workflow optimization, **test-generator** for replacing flaky tests with deterministic ones, and **docker-helper** for build performance. The approach: profile what's slow, identify what's flaky, fix both, then monitor for regression.

## Step-by-Step Walkthrough

### Step 1: Profile the Pipeline

First, figure out where the 43 minutes are actually going.

```text
Analyze our GitHub Actions pipeline. Where are the 43 minutes going and which tests are flaky?
```

The time breakdown reveals four distinct bottlenecks:

| Phase | Time | % of Total | Root Cause |
|---|---|---|---|
| `npm install` | 8m 47s | 20% | No dependency cache configured |
| Test suite | 18m 33s | 43% | Running serially in a single shard |
| Docker build | 7m 48s | 18% | No layer cache, rebuilds from scratch |
| Other (checkout, lint, upload) | 8m 04s | 19% | Minor optimizations possible |

The flaky test analysis is even more telling:

| Test File | Fail Rate | Root Cause |
|---|---|---|
| `checkout.spec.ts:42` | 34% | `setTimeout` race with Stripe webhook |
| `search.spec.ts:78` | 28% | Elasticsearch refresh lag |
| `websocket.spec.ts:15` | 23% | Hardcoded port collision |
| `email.spec.ts:31` | 19% | SMTP mock not ready before assertion |
| `cache.spec.ts:56` | 12% | Redis connection race in setup |
| 9 more tests | 5-10% each | Various timing assumptions |

Combined, these 14 tests produce the 72% flake rate. Fix them all and the pipeline should stabilize to around 97% pass rate.

### Step 2: Fix the Flaky Tests

Every flaky test has the same underlying pattern: it assumes something will be ready by a certain time instead of verifying it.

```text
Fix all 14 flaky tests with deterministic replacements.
```

The fixes follow a few recurring patterns:

- **`setTimeout` races** (4 tests): Replace `setTimeout(1000)` with `waitForCondition()` polling that checks the actual state every 50ms with a 5-second timeout. The checkout test was waiting a fixed 1 second for a Stripe webhook -- sometimes Stripe responds in 200ms, sometimes 1.5 seconds.
- **Stale reads** (3 tests): Add explicit `await index.refresh()` calls before asserting against Elasticsearch. The search test was reading before the index caught up.
- **Port collisions** (2 tests): Replace hardcoded `port: 3001` with `port: 0` to let the OS assign a random available port. Two test files were fighting over the same port when running concurrently.
- **Unready mocks** (3 tests): Await the mock server's `listening` event before running assertions. The email test was sending requests before the SMTP mock finished binding.
- **Connection races** (2 tests): Move `await redis.connect()` into `beforeEach` instead of fire-and-forget in module initialization.

Validation: the full suite runs 20 consecutive times -- 20 out of 20 green. Previously it was about 5 out of 20.

### Step 3: Optimize Build Performance

With flakiness fixed, the pipeline is reliable but still slow. Three changes cut 43 minutes to under 11.

```text
Add dependency caching, parallelize tests, and optimize Docker builds.
```

**Dependency cache**: Add `actions/cache` keyed on the `package-lock.json` hash. First run populates the cache; every subsequent run with the same lockfile skips `npm install` entirely. Time drops from 8m 47s to 12 seconds.

**Parallel test shards**: Split the test suite across 3 parallel GitHub Actions jobs. Each shard runs roughly one-third of the tests. Total wall-clock time is the slowest shard: 4m 11s instead of 18m 33s serial.

**Docker layer cache**: Enable BuildKit with `docker/build-push-action` and GitHub Actions cache backend. When dependencies haven't changed (the common case), the build reuses cached layers. Time drops from 7m 48s to 1m 22s.

The result:

| Metric | Before | After |
|---|---|---|
| Average build time | 43m 12s | 10m 47s |
| Flake rate | 28% (72% chance of at least one flake) | ~3% |
| Monthly CI cost | $840 | $310 |
| Engineering hours wasted per week | 22 | ~3 |

### Step 4: Add Monitoring and Alerts

A pipeline that degrades slowly is worse than one that breaks loudly, because nobody notices until it's bad again. Monitoring prevents the backslide.

```text
Alert us if build times regress or flake rate increases.
```

Two monitoring channels go live:

**Weekly Slack report** (`#engineering`, Monday 9 AM): Average build time (target <15m), pass rate (target >95%), flaky tests detected, re-runs needed, and monthly cost. A single glanceable summary that catches drift before it becomes a problem.

**Instant alerts** (`#ci-alerts`): Fires immediately if any single build exceeds 20 minutes, if main fails 3 times consecutively, or if any test fails 3 or more times in a single day. These catch acute regressions -- a new test that introduces flakiness or a dependency change that blows up cache hits.

### Step 5: Document Pipeline Standards

The fixes are only permanent if the team knows the rules. A CI playbook prevents new contributions from reintroducing the same problems.

```text
Create a playbook so new tests don't introduce flakiness.
```

The playbook (`docs/CI-PLAYBOOK.md`) codifies what the team learned:

- **Performance budgets**: Total pipeline under 15 minutes, test suite under 5 minutes per shard, Docker build under 2 minutes cached
- **Non-flaky test rules**: No `setTimeout` waits (use polling helpers), random ports for test servers, isolated database state via transaction rollback, no live API calls in CI
- **New test validation**: Run 10 times locally before pushing -- if it fails once, it's flaky

## Real-World Example

An engineering manager at a Series A data infrastructure startup inherited this exact situation. Eleven engineers, 8-10 PRs daily, 38-minute builds, 31% flake rate. Engineers had stopped trusting CI entirely -- some merged after a single green run even following three consecutive flaky failures.

On Tuesday, the pipeline profiling revealed the same pattern: no caching, serial tests, Docker rebuilding from scratch every time. 72% of build time was recoverable. Flake analysis found 11 tests with identical root causes -- race conditions and timing assumptions baked in months ago. By Thursday, all flaky tests were fixed, 3-shard parallel CI was running with dependency and layer caching enabled.

The result: 38 minutes dropped to 9. The team went a full week without a flaky failure -- unprecedented in the project's history. Over the following month, PR velocity increased 23%, CI costs dropped from $920 to $280 per month, and "CI issues" disappeared from sprint retrospectives entirely. Engineers started pushing smaller, more frequent PRs because the feedback loop was finally fast enough to support it. The optimization recovered an estimated 2.5 engineering weeks per month -- time that went back into building features instead of babysitting builds.
