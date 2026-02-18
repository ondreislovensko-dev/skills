---
title: "Set Up a Production Load Balancer with SSL and Traffic Management"
slug: set-up-production-load-balancer
description: "Configure Nginx as a reverse proxy with SSL termination, load balancing, rate limiting, and WebSocket support to handle production traffic reliably."
skills: [load-balancer, cicd-pipeline]
category: devops
tags: [nginx, load-balancer, ssl, reverse-proxy, devops, rate-limiting]
---

# Set Up a Production Load Balancer with SSL and Traffic Management

## The Problem

Ravi runs platform engineering at a 40-person fintech startup. Their API runs on three backend servers behind a single server with no load balancing — traffic hits one box, and when it goes down at 2 AM, everything goes down. There is no SSL termination (the app handles it), no rate limiting (a bot scraped their public API and caused a 20-minute outage last month), and no health checks (a zombie process on one server returned 502s for hours before anyone noticed).

They need a proper traffic layer: load balance across backends, terminate SSL in one place, rate limit abusive clients, proxy WebSocket connections for their real-time dashboard, and automatically stop routing to unhealthy servers.

## The Solution

Use the **load-balancer** skill to configure Nginx as a reverse proxy with upstream groups, SSL, rate limiting, and health checks. Use the **cicd-pipeline** skill to automate config deployment and reload on changes.

## Step-by-Step Walkthrough

### Step 1: Assess Current Setup and Design the Architecture

```text
I have 3 backend servers running a Node.js API on port 8080 (api1, api2, api3).
api1 and api2 are the same spec (4 vCPU, 8GB RAM), api3 is smaller (2 vCPU, 4GB)
and should get less traffic. I also have a WebSocket service for real-time updates
on ws1 and ws2, port 8080. I need Nginx in front of everything with: HTTPS on
api.example.com, load balancing across the 3 API servers, WebSocket proxying on
/ws/, rate limiting for the public API (30 req/s per IP, but auth endpoints at
5 req/min), and health checks. Design the Nginx configuration.
```

The architecture is straightforward: all client traffic hits Nginx on port 443 with SSL, and Nginx routes it to the right upstream group.

```
Client --> Nginx (443/SSL) --> upstream app_servers (3 backends)
                           --> upstream ws_servers (2 backends)
```

Two upstream groups handle different traffic patterns:

**app_servers** uses `least_conn` algorithm with weighted backends. api1 and api2 get `weight=3`, api3 gets `weight=2` — proportional to their resources, so the smaller box gets roughly 33% less traffic. Passive health checks with `max_fails=3` and `fail_timeout=30s` automatically remove failing servers.

**ws_servers** uses `ip_hash` for sticky sessions — WebSocket connections need to stay on the same backend for the lifetime of the connection.

Rate limiting is split by path:
- `/api/*` — 30 requests/second per IP, burst of 20
- `/api/auth/*` — 5 requests/minute per IP, burst of 3 (brute force protection)
- `/ws/*` — no rate limit (persistent connections)

The configuration generates two files: `/etc/nginx/nginx.conf` with the upstream definitions and `/etc/nginx/conf.d/api.conf` with the server block and all location rules.

### Step 2: Set Up SSL with Let's Encrypt

```text
Set up Let's Encrypt SSL for api.example.com on this Nginx server. Configure
auto-renewal that reloads Nginx after certificate refresh. Use the webroot method
since Nginx is already running. Also set up OCSP stapling for faster TLS handshakes.
```

Certificate provisioning:

```bash
certbot certonly --webroot -w /var/www/certbot -d api.example.com
```

The Nginx SSL block locks down the TLS configuration:

```nginx
ssl_certificate     /etc/letsencrypt/live/api.example.com/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;
ssl_protocols       TLSv1.2 TLSv1.3;
ssl_stapling        on;
ssl_stapling_verify on;
```

Auto-renewal runs via cron at 3 AM daily: `certbot renew --quiet --post-hook "nginx -s reload"`. All HTTP traffic gets a 301 redirect to HTTPS. Security headers are added — `Strict-Transport-Security` with a 2-year max-age, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`. The result: an A+ rating on SSL Labs.

### Step 3: Configure Health Checks and Failover

```text
Add proper health checks. Each API server has a /health endpoint that returns
200 when healthy and checks database connectivity. If a server fails 3 health
checks in a row, stop routing traffic to it. When it recovers, gradually
reintroduce it. Also configure Nginx to retry the next upstream server if it
gets a 502 or 503 from a backend.
```

Nginx's passive health checks handle the detection: after 3 consecutive failures, a server is marked down for 30 seconds. Traffic redistributes automatically to the remaining healthy servers.

The transparent retry is the part users never see:

```nginx
proxy_next_upstream error timeout http_502 http_503;
proxy_next_upstream_tries 2;
```

If a backend returns 502 or 503, Nginx silently retries on the next server. The client sees no error unless all three servers fail. This single directive would have prevented the 3-hour 502 incident from last month — the zombie process would have been bypassed automatically.

One limitation: Nginx OSS doesn't support native slow-start (gradually ramping traffic to a recovered server). The workaround is weight adjustment during maintenance windows. For teams that need slow-start, HAProxy offers a `slowstart 60s` directive that handles it natively.

Monitoring is added via the access log: `$upstream_response_time` tracks how long each backend takes. An alert fires when upstream response time exceeds 2 seconds for 5 minutes — catching slow backends before they become unresponsive ones.

### Step 4: Test Rate Limiting and Attack Resilience

```text
Test the rate limiting configuration. Simulate: 1) normal API traffic at
20 req/s from a single IP, 2) burst traffic at 50 req/s, 3) brute force
login attempts at 10 req/s on /api/auth/login. Show me the expected
behavior for each scenario.
```

Three scenarios validate the rate limiting configuration:

**Normal traffic (20 req/s):** 200 out of 200 requests pass. All under the 30 req/s limit, no intervention needed.

**Burst traffic (50 req/s, 100 requests):** The first 50 requests pass (burst buffer of 20 plus the 30/s rate absorbs them). Of the next 50, only 30 pass — the remaining 20 get HTTP 429 Too Many Requests. The burst parameter handles legitimate traffic spikes without blocking real users.

**Login brute force (10 req/s on /api/auth/login):** The first 3 requests pass (burst=3), then requests 4 through 10 all return 429. After 60 seconds, the next request passes. An attacker is effectively limited to 5 attempts per minute — making brute force impractical.

Edge cases verified: rate limits are per-IP (`$binary_remote_addr`), different IPs are independently limited, and WebSocket paths are excluded from rate limiting entirely.

### Step 5: Automate Config Deployment with CI/CD

```text
Create a GitHub Actions workflow that: validates Nginx config syntax on every PR
(nginx -t), deploys updated configs to the Nginx server on merge to main, and
reloads Nginx gracefully (no dropped connections). Store the Nginx configs in
a nginx/ directory in our infrastructure repo.
```

The pipeline at `.github/workflows/nginx-deploy.yml` has two stages:

**On PR:** Spins up an Nginx container, copies the config files from the `nginx/` directory, and runs `nginx -t` for syntax validation. Comments on the PR with the result. Bad config never reaches production.

**On merge to main:** SSH to the load balancer server, rsync the `nginx/` directory to `/etc/nginx/`, run `nginx -t` on production (verify before applying), then `nginx -s reload` for a graceful reload. The reload is the key detail — it finishes serving in-flight requests on the old config while new requests use the updated config. Zero dropped connections.

If anything fails, the rollback restores the previous config from git and reloads. A Slack notification confirms success or failure.

## Real-World Example

Ravi inherits a setup where three API servers sit behind a single point of failure with no load balancing, no SSL termination, and no rate limiting. Last month a scraper bot took down the API for 20 minutes, and a zombie backend process returned 502s for 3 hours before anyone noticed.

He configures Nginx as a reverse proxy with weighted load balancing across 3 servers, giving the smaller server proportionally less traffic. SSL is set up with Let's Encrypt auto-renewal and an A+ SSL Labs rating. Health checks catch a failing backend within 90 seconds and transparently reroute traffic with no customer impact. Rate limiting stops bot abuse: the general API at 30 req/s per IP, the login endpoint at 5 req/min.

A CI/CD pipeline validates every config change on PR and deploys with zero-downtime reload on merge. The next time a backend server has issues, traffic shifts automatically. The bot that caused last month's outage now gets 429 responses while legitimate users are unaffected.
