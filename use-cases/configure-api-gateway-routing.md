---
title: "Configure API Gateway Routing with AI"
slug: configure-api-gateway-routing
description: "Design and implement API gateway routing rules, rate limiting, and request transformation for microservices architectures."
skills: [coding-agent, docker-helper, api-tester]
category: devops
tags: [api-gateway, routing, microservices, nginx, kong]
---

# Configure API Gateway Routing with AI

## The Problem

Your microservices architecture has grown to 8 services, and it shows. Every frontend request hits a different port or subdomain. CORS is configured inconsistently across services — last month a billing-service misconfiguration allowed any origin to make requests for two full days before anyone noticed. Authentication middleware is copy-pasted into each service with slight variations. There is no centralized rate limiting, so a misbehaving client can hammer any service directly.

Adding a new service means updating the frontend, the nginx config, the CORS whitelist, and the load balancer. This process takes a full day, and it has caused three outages in the past six months from misconfigured routing rules. Every new developer spends their first week understanding which service handles what and which port to call.

## The Solution

Using the **coding-agent**, **docker-helper**, and **api-tester** skills, the agent designs a complete API gateway configuration with Kong, generates routing rules with per-route rate limiting and JWT auth, produces a test suite to validate everything before deployment, and creates a zero-downtime migration plan.

## Step-by-Step Walkthrough

### Step 1: Describe the Current Service Landscape

```text
We have 8 microservices running in Docker:
- auth-service (:4001) - login, signup, token refresh
- user-service (:4002) - profiles, preferences
- billing-service (:4003) - subscriptions, invoices
- notification-service (:4004) - email, push, webhooks
- upload-service (:4005) - file uploads, media processing
- search-service (:4006) - full-text search
- analytics-service (:4007) - event tracking, dashboards
- admin-service (:4008) - internal admin panel

Currently the frontend calls each service directly. Set up an API gateway
that consolidates everything under a single domain with proper routing,
auth, and rate limiting.
```

### Step 2: Design the Routing Table

The routing table consolidates 8 service URLs into a single domain with clear access patterns:

**Public routes (require JWT):**

| Path | Service | Rate Limit |
|---|---|---|
| `/api/users/*` | user-service:4002 | 200 req/min per user |
| `/api/billing/*` | billing-service:4003 | 200 req/min per user |
| `/api/notifications/*` | notification-service:4004 | 200 req/min per user |
| `/api/uploads/*` | upload-service:4005 | 20 req/min per user |
| `/api/search/*` | search-service:4006 | 60 req/min per user |

**Public routes (no auth):**

| Path | Service | Rate Limit |
|---|---|---|
| `/api/auth/*` | auth-service:4001 | 10 req/min per IP (login) |
| `/api/health` | Gateway health aggregation | -- |

**Internal routes (API key required):**

| Path | Service | Notes |
|---|---|---|
| `/api/analytics/*` | analytics-service:4007 | Server-to-server only |
| `/internal/admin/*` | admin-service:4008 | Internal network only |

The upload service gets a tighter rate limit (20/min) to prevent abuse. The login endpoint is rate-limited by IP rather than user (since there is no auth token yet) to block brute-force attacks. Search is capped at 60/min because each query is expensive.

### Step 3: Generate the Kong Configuration

```yaml
# kong.yml (declarative configuration)
_format_version: "3.0"

services:
  - name: auth-service
    url: http://auth-service:4001
    routes:
      - paths: ["/api/auth"]
        strip_path: true
    plugins:
      - name: rate-limiting
        config: { minute: 10, policy: redis, limit_by: ip }

  - name: user-service
    url: http://user-service:4002
    routes:
      - paths: ["/api/users"]
        strip_path: true
    plugins:
      - name: jwt
      - name: rate-limiting
        config: { minute: 200, policy: redis }

  - name: upload-service
    url: http://upload-service:4005
    routes:
      - paths: ["/api/uploads"]
        methods: ["GET", "POST", "DELETE"]
    plugins:
      - name: jwt
      - name: rate-limiting
        config: { minute: 20 }
      - name: request-size-limiting
        config: { allowed_payload_size: 50 }  # 50MB max

# Global plugins applied to all routes
plugins:
  - name: cors
    config:
      origins: ["https://app.example.com"]
      methods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
      headers: ["Authorization", "Content-Type"]
      max_age: 3600
```

CORS is configured exactly once, at the gateway level. No more per-service CORS headers to keep in sync. JWT validation happens at the gateway — services behind it receive pre-validated requests with the user ID injected as a header, so they never touch auth logic directly.

### Step 4: Validate with a Comprehensive Test Suite

The test suite covers 47 cases across four categories:

**Route resolution (8 tests):** every service is reachable through its gateway path, and path stripping works correctly (the service receives `/profiles/123`, not `/api/users/profiles/123`).

**Auth enforcement (12 tests):** protected routes return 401 without a JWT. The auth service itself is accessible without a token. Invalid tokens get 403. Expired tokens get 401 with a clear error message.

**Rate limiting (8 tests):** each route enforces its configured limit. Exceeding the limit returns 429 with a `Retry-After` header. Different users have independent limits.

**Security (19 tests):** CORS headers are correct for browser requests. Internal API key headers are stripped from responses (so they don't leak to the client). Services return 503 through the gateway when they are down, not a raw connection error.

Results from the first run: 45 passed, 2 warnings. The warnings catch an upload service endpoint missing `Content-Length` validation for multipart uploads, and the analytics service leaking the internal API key header in responses. Both are fixed before deployment.

### Step 5: Deploy with Zero-Downtime Migration

The migration runs in five phases, with a rollback plan at every step:

1. **Deploy gateway** alongside existing direct connections — both work simultaneously
2. **Canary at 10%** — route a tenth of traffic through the gateway, watch error rates
3. **Monitor for 24 hours** — compare error rates, latency, and response shapes between direct and gateway traffic
4. **Route 100%** — switch all traffic to the gateway
5. **Remove direct exposure** — remove service ports from the load balancer

Rollback at any phase: DNS switch back to direct service endpoints, takes less than 5 minutes.

The frontend changes are minimal: replace 8 service base URLs with a single `GATEWAY_URL`, remove per-service CORS handling, and remove client-side auth header injection (the gateway handles it now). The frontend codebase shrinks by about 200 lines of service-discovery boilerplate.

## Real-World Example

Jonas deploys the gateway using the canary migration plan, routing 10% of traffic through Kong on day one. The monitoring dashboard shows identical error rates between direct and gateway traffic, so he bumps it to 50% on day two and 100% on day three.

After full migration, three things change immediately. First, CORS is handled in one place — the billing-service vulnerability that went unnoticed for two days would have been impossible because the gateway enforces a single origin whitelist. Second, onboarding new developers takes half the time because there is one domain to learn, not eight ports to memorize. Third, the rate limiting on the login endpoint catches a brute-force attempt within the first week — something that was completely invisible before.

The frontend team removes 200 lines of service-discovery code and the per-service auth header injection that was slightly different in three of the eight services. Adding a new service now takes 15 minutes instead of a full day: add a service block to `kong.yml`, run the test suite, and deploy.
