---
title: "Build an Internal Status Page for Services"
slug: build-internal-status-page
description: "Create a real-time internal status page that monitors service health, displays incident timelines, and reduces status-check interruptions."
skills: [coding-agent, frontend-design, api-tester]
category: devops
tags: [status-page, monitoring, uptime, incidents, internal-tools]
---

# Build an Internal Status Page for Services

## The Problem

Your team runs 8 microservices, 3 databases, a message queue, and 2 third-party integrations. When something goes down, the first 10 minutes are wasted on triage: "Is it the API or the database?" "Is Stripe down or is it us?" "Is staging broken too?" Engineers ping each other on Slack, the support team asks for status updates, and the PM wants an ETA -- all before anyone has started actually debugging.

The "is X down?" messages in Slack have become a running joke. Last week, the payments service went down because Stripe had an outage. Five engineers independently investigated for 15 minutes before someone checked Stripe's status page and realized it was not an internal problem. That is over an hour of senior engineering time wasted because there was no single place to look.

Public status page services like Statuspage or Instatus cost $79-299/month and are designed for customer-facing communication -- clean, minimal, and deliberately vague. Internal engineering needs are different: auto-detection of service health, a dependency graph that shows cascading failures at a glance, and enough context that the on-call engineer can start the right runbook immediately instead of playing detective.

## The Solution

Using the **coding-agent**, **frontend-design**, and **api-tester** skills, the agent builds a health check system that probes all 14 components every 30 seconds, a dashboard with dependency graphs and incident timelines, and automated Slack alerting with enough context to skip the triage phase entirely.

## Step-by-Step Walkthrough

### Step 1: Map Services and Health Endpoints

Start by cataloging every component and what "healthy" means for each one:

```text
List all our services, their health check endpoints, dependencies, and what "healthy" means for each. Include databases, queues, and third-party services.
```

The service map covers 14 components across three tiers:

| Tier | Components |
|------|-----------|
| **Services** (6) | api-gateway, auth, orders, payments, worker, frontend |
| **Infrastructure** (5) | postgresql-primary, postgresql-replica, redis-cache, rabbitmq |
| **Third-party** (3) | stripe-api, sendgrid, s3-storage |

Each component gets a health endpoint, response time threshold, and dependency mapping. The dependency graph is the critical piece: `orders` depends on postgresql, redis, and rabbitmq. `payments` depends on postgresql and stripe. `worker` depends on redis, rabbitmq, sendgrid, and s3. When postgresql-primary goes down, the status page immediately shows that orders, payments, and worker are affected -- before anyone needs to investigate manually.

The third-party checks are particularly valuable. Stripe, SendGrid, and S3 each have public status pages, but nobody checks them during an incident. The status page probes their APIs directly and can distinguish "our payments code is broken" from "Stripe is having an outage" in 30 seconds.

### Step 2: Build the Health Check System

```text
Create a health check runner that probes all 14 components every 30 seconds. Store results with latency and error details. Detect degraded states, not just up/down.
```

The checker runs three types of probes in parallel every 30 seconds:

- **HTTP probe** -- for services and third-party APIs. Checks status code, response time, and optionally validates response body content
- **TCP probe** -- for databases and Redis. Verifies connection and measures round-trip latency
- **Custom probe** -- for service-specific metrics like RabbitMQ queue depth, PostgreSQL replication lag, and Redis memory usage

Health states go beyond simple up/down, because "degraded" is often more useful than "down":

| State | Meaning | Example |
|-------|---------|---------|
| **Operational** | All checks pass, latency within normal range | API responding in 45ms (baseline: 50ms) |
| **Degraded** | Passing but latency exceeds 2x baseline, or partial failures | API responding in 340ms (baseline: 50ms) |
| **Partial Outage** | Some checks failing, service still responding | 2 of 5 health check endpoints failing |
| **Major Outage** | Health check failing or timing out | No response after 10s timeout |

Results store in SQLite for the last 30 days of history, and a Slack webhook fires on every state change -- so the team learns about problems from the status page, not from user complaints.

### Step 3: Build the Dashboard

```text
Create a clean status page dashboard showing all services, current status, uptime percentages, and a 90-day incident timeline. Make it fast-loading and auto-refreshing.
```

The dashboard has five panels designed for two audiences: the on-call engineer who needs to diagnose quickly, and the team lead who needs to track reliability over time.

- **Service Grid** -- color-coded status indicators for all 14 components, grouped by tier. Green, yellow, orange, or red at a glance.
- **Dependency Graph** -- visual map showing service relationships and current state. When postgresql-primary goes red, the downstream services (orders, payments, worker) immediately show their dependency is unhealthy. This is the panel that saves the most triage time.
- **Uptime Bars** -- 90-day history per service. Click any day to see incidents that occurred. The bars make reliability trends obvious: is this service getting more or less stable over time?
- **Latency Sparklines** -- 24-hour trend lines per service. A gradually increasing latency curve often predicts an outage hours before it happens.
- **Incident Timeline** -- current and past incidents with duration, impact scope, and resolution notes.

The frontend auto-refreshes via Server-Sent Events (no polling), is mobile responsive for on-call engineers checking from their phone at 3 AM, includes dark mode by default, and ships under 100KB. No framework -- just vanilla HTML, CSS, and JavaScript, so it loads instantly even on a slow connection.

### Step 4: Add Incident Management

```text
Add incident creation and tracking. When a service goes red, auto-create an incident. Let engineers add updates and mark resolved.
```

Incidents can be created two ways:

**Automatic:** when a service enters Major Outage state, an incident is created and impact is calculated from the dependency graph. If postgresql-primary goes down, the incident immediately lists orders, payments, and worker as affected services -- without anyone needing to investigate the blast radius manually.

**Manual:** engineers create, update, and resolve incidents via `/incident create|update|resolve` in Slack or directly through the dashboard. Manual incidents cover situations the health checks cannot detect, like data integrity issues or degraded functionality that still passes health checks.

A typical incident timeline:

> **14:32** -- payments-service enters Major Outage. Incident auto-created, Slack alert sent to `#engineering`.
> **14:38** -- Engineer adds update: "Stripe returning 503, monitoring their status page."
> **15:12** -- payments-service recovers. Incident auto-resolved. Duration: 40 minutes.

After resolution, the system generates an incident summary with the full timeline, all affected services, total duration, and any updates posted during the incident -- ready for the post-mortem document.

### Step 5: Deploy and Configure Alerts

```text
Deploy the status page internally. Set up Slack alerts for state changes and a daily health summary.
```

Deployment is a single Docker Compose stack at `status.internal.company.com` -- one container for the checker, one for the web dashboard, and the SQLite database stored on a volume.

**Real-time alerts to Slack:**
- State change: `#engineering` -- "orders-service: Major outage (dependency: postgresql-primary unhealthy)"
- Degraded for 5+ minutes: `#on-call` -- "postgresql-replica lag >5s (threshold: 2s)"
- Recovery: `#engineering` -- "orders-service recovered (duration: 12min)"

**Daily summary at 9:00 AM:**
> All services operational. 24h uptime: 99.97%. postgresql-replica had 8min degradation at 03:14 (auto-recovered). Slowest service: payments-service (avg latency: 340ms, +15% vs 7-day baseline).

**Weekly report:** uptime percentages per service, incident count, mean time to recovery, and reliability trends. This report feeds directly into the team's SLO tracking.

## Real-World Example

Oscar, a platform engineer at a 20-person SaaS startup, spent the first 10 minutes of every incident figuring out what was actually broken. The team ran 8 services with complex dependencies, and Slack was the unofficial status page -- "is X down?" messages flooded `#engineering` multiple times a week.

He built the internal status page in an afternoon. The health check system probes all 14 components every 30 seconds. The dependency graph shows cascading failures at a glance -- when a database goes down, every dependent service lights up immediately. The health checks distinguish between "down" and "degraded," catching slow responses and replication lag before they become outages.

The following Monday, the PostgreSQL replica fell behind. The status page caught it in 30 seconds, auto-created an incident, and sent a Slack alert with context: "postgresql-replica degraded -- replication lag 12s, affects: read-heavy queries in orders-service." The on-call engineer opened the dashboard, saw exactly which services were impacted via the dependency graph, and started the right runbook immediately. No Slack detective work, no pinging colleagues, no investigating the wrong service. "Is X down?" messages in Slack dropped to near zero. Average time-to-diagnosis went from 10 minutes to under 2.
