---
title: "Implement Rate Limiting and API Abuse Protection with AI"
slug: implement-rate-limiting-and-api-abuse-protection
description: "Set up layered rate limiting and abuse detection for your API endpoints using AI-guided configuration."
skills: [rate-limiter, security-audit]
category: devops
tags: [rate-limiting, api-security, abuse-protection, middleware, express]
---

# Implement Rate Limiting and API Abuse Protection with AI

## The Problem

Your API is live, traffic is growing, and you're seeing suspicious patterns — one IP hammering your login endpoint 200 times per minute, a bot scraping your product catalog, trial users burning through expensive third-party API credits. You know you need rate limiting, but the decisions are complex: per-user vs per-IP vs per-endpoint limits, choosing the right algorithm (sliding window? token bucket?), handling distributed deployments with Redis, returning proper 429 responses, and not accidentally blocking legitimate users behind shared NATs.

## The Solution

Use the **rate-limiter** skill to generate production-ready middleware with layered limits, and the **security-audit** skill to verify the implementation catches real abuse patterns. Install both skills:

```bash
npx terminal-skills install rate-limiter security-audit
```

## Step-by-Step Walkthrough

### 1. Analyze your API surface and traffic patterns

```
Review my Express API in src/routes/. Identify all public endpoints and classify them by sensitivity: auth endpoints (login, register, password-reset), data-read endpoints, data-write endpoints, and webhook receivers. For each category, recommend appropriate rate limits based on typical SaaS usage patterns.
```

The agent scans your route files and produces a classification:

```
Endpoint Analysis:
- POST /auth/login         → Auth (critical) — recommend 5 req/min per IP
- POST /auth/register      → Auth (critical) — recommend 3 req/min per IP  
- POST /auth/reset-password → Auth (critical) — recommend 2 req/min per IP
- GET  /api/products       → Data-read — recommend 60 req/min per user
- GET  /api/products/:id   → Data-read — recommend 60 req/min per user
- POST /api/orders          → Data-write — recommend 20 req/min per user
- POST /webhooks/stripe     → Webhook — recommend 100 req/min per IP (Stripe IPs)
```

### 2. Generate the rate limiting middleware

```
Create a rate limiting middleware using a sliding window algorithm backed by Redis. Implement three layers: a global per-IP limit of 200 req/min, endpoint-specific limits from the classification above, and an authenticated-user daily quota of 10,000 requests. Include proper 429 responses with Retry-After headers and X-RateLimit-* headers on every response.
```

The agent generates `src/middleware/rateLimiter.ts` with Redis-backed sliding window counters, a configuration map for endpoint-specific limits, and middleware that chains the three layers.

### 3. Add abuse detection patterns

```
Add an abuse detection layer that identifies and temporarily blocks: IPs that hit rate limits more than 10 times in 5 minutes, requests with missing or rotating User-Agent headers across rapid requests, and credential stuffing patterns on auth endpoints (many different usernames from the same IP). Store blocked IPs in Redis with a 15-minute TTL and log all blocks with request metadata to a structured JSON log.
```

### 4. Verify with a security audit

```
Run a security audit on the rate limiting implementation. Check for: bypass via X-Forwarded-For header spoofing, race conditions in the Redis counter logic, whether the blocking can be used for DoS against legitimate users (IP blocking in shared NAT scenarios), and proper handling when Redis is unavailable. Suggest fixes for any issues found.
```

The agent identifies that `X-Forwarded-For` is trusted without validation and recommends configuring Express `trust proxy` properly with a known proxy list. It also flags the missing Redis connection failure fallback and generates a graceful degradation path using in-memory limits.

### 5. Add monitoring and alerting

```
Create a monitoring dashboard config for the rate limiter. Generate Prometheus metrics for: total requests by endpoint and status, rate limit hits by category, blocked IPs count, and Redis latency. Add a Grafana dashboard JSON that shows these metrics with alerts when rate limit hits spike above 3x the hourly average.
```

## Real-World Example

A backend engineer at a mid-stage fintech startup notices their `/auth/login` endpoint receiving 3,000 requests per minute from a small set of IPs — a credential stuffing attack. They have no rate limiting beyond what their cloud load balancer offers, and that's too coarse.

1. They ask the agent to analyze their 14 API endpoints and classify them by risk
2. The agent generates a Redis-backed rate limiter with sliding window counters, deployed as Express middleware in under 2 minutes
3. The abuse detection layer catches the stuffing pattern (50+ unique usernames from one IP in 60 seconds) and auto-blocks the offending IPs
4. The security audit catches that their Kubernetes ingress means `X-Forwarded-For` has multiple IPs and the middleware was reading the wrong one
5. Within an hour, they have production-grade rate limiting with Grafana dashboards showing real-time abuse metrics

The attack traffic drops to zero blocked requests within 20 minutes of deployment. Legitimate users experience no impact.

## Related Skills

- [security-audit](../skills/security-audit/) — Validates rate limiting logic for bypass vulnerabilities
- [cicd-pipeline](../skills/cicd-pipeline/) — Integrates rate limit config testing into deployment pipelines
