---
title: "Plan Multi-Region Deployment Strategy with AI"
slug: plan-multi-region-deployment
description: "Design and implement a multi-region deployment architecture for improved latency, reliability, and compliance."
skills: [coding-agent, docker-helper, hetzner-cloud]
category: devops
tags: [multi-region, deployment, infrastructure, high-availability, latency]
---

# Plan Multi-Region Deployment Strategy with AI

## The Problem

Priya is the CTO of a 15-person SaaS startup that just signed an enterprise deal with a German logistics company. The contract requires EU data residency and 99.9% uptime. The problem: everything runs on a single Hetzner server in Virginia.

European users experience 200ms+ latency on every API call. Australian customers complain about slow page loads. A single-region outage last quarter took the entire product offline for 45 minutes — which, under a 99.9% SLA, burns through the entire quarterly error budget in one incident.

Multi-region is the obvious answer, but the complexity feels overwhelming for a 15-person team. Database replication across regions. Latency-based DNS routing. Coordinated deployments that don't break when one region is mid-update. Data sovereignty rules that dictate where specific users' data physically lives. Each of these is a project in itself, and Priya needs all of them working together within a $2,000/month infrastructure budget.

## The Solution

Using the **coding-agent**, **docker-helper**, and **hetzner-cloud** skills, the approach is to design the topology, generate infrastructure-as-code for all three regions, containerize services for portable deployment, configure database replication, set up latency-based routing, and build a deployment pipeline that rolls changes region by region with automatic rollback.

## Step-by-Step Walkthrough

### Step 1: Define Requirements and Constraints

```text
We run a Next.js frontend and Express API with Postgres. Currently single-region
in US East. We need to expand to Europe (Frankfurt) and Asia (Singapore) for:
- Lower latency for global users
- EU data residency for GDPR compliance
- High availability (survive a full region outage)
Our budget for infrastructure is $2,000/month. Help me plan this.
```

The budget constraint is the most important input. Multi-region on AWS or GCP with managed databases could easily cost $5,000-10,000/month. Hetzner makes it feasible at $2,000 — but that means self-managing database replication instead of relying on managed services. The tradeoff is explicit: lower cost in exchange for more operational responsibility.

### Step 2: Design the Multi-Region Architecture

The architecture uses an active-active topology for US and EU (both handle reads and writes), with Asia as a read replica region. This keeps costs manageable while covering the three main requirements: low latency, data residency, and high availability.

**US East (Primary):**
- 2x CX41 API servers, load balanced
- Postgres primary (CPX41 + 200GB volume)
- Redis primary

**EU Frankfurt:**
- 2x CX41 API servers, load balanced
- Postgres replica with promotion capability
- Redis replica
- EU user data stays in this region (GDPR compliance)

**Asia Singapore:**
- 1x CX31 API server (lower traffic volume)
- Postgres read replica
- Redis cache (local, no replication needed)

**Routing:** Cloudflare DNS with latency-based routing sends users to the nearest region automatically. If a region goes down, Cloudflare health checks detect it within 30 seconds and reroute traffic.

**Estimated cost: $1,740/month** — under budget with room for a monitoring stack or emergency scaling.

The active-active US/EU design is the key decision. A simpler active-passive setup would be cheaper, but it wouldn't satisfy the GDPR requirement — EU user data needs to be writable in Frankfurt, not just readable. Asia gets a smaller footprint because the user base there is 5x smaller than US or EU.

### Step 3: Generate Infrastructure-as-Code

The Terraform configuration organizes into reusable modules so each region is defined by variables, not copied code:

```
terraform/
  modules/
    region/          # Reusable per-region module (servers, LB, firewall)
    database/        # Postgres with streaming replication
    networking/      # VPC, firewall rules, WireGuard mesh VPN
  environments/
    us-east.tf       # Primary region config
    eu-frankfurt.tf  # EU region config
    ap-singapore.tf  # Asia region config
  dns.tf             # Cloudflare latency-based routing
  variables.tf
```

Key architectural decisions embedded in the code:

- **WireGuard mesh VPN** between all three regions for encrypted database replication traffic. This avoids exposing Postgres ports to the public internet and adds roughly 2ms of overhead per packet — negligible for replication.
- **PgBouncer** connection pooling at each region to handle cross-region database connections efficiently. Without pooling, the connection setup overhead on 200ms links would add up fast, especially during traffic spikes.
- **Blue-green deployment** per region with health checks — each region can be updated independently without affecting the others. Old and new versions coexist briefly during the switchover.

### Step 4: Build Deployment Orchestration

Deployments roll region by region, starting with the lowest-traffic region:

```bash
# deploy.sh workflow:
# 1. Deploy to Asia (lowest traffic) -> run smoke tests
# 2. Deploy to EU -> run smoke tests + check replication lag
# 3. Deploy to US (primary) -> run full integration tests
# 4. If any region fails: automatic rollback of that region only
```

This is where multi-region gets subtle. A bad deploy to Asia doesn't affect US or EU users — the rolling strategy contains blast radius to the smallest user population first. The replication lag check after the EU deploy is critical: if a database migration causes replication to break, it's caught before the primary region gets the update.

Three levels of health checks validate each deployment:

| Endpoint | What It Checks | Failure Action |
|---|---|---|
| `/health/basic` | Application running, can serve requests | Rollback immediately |
| `/health/db` | Database connected, replication lag < 500ms | Pause deploy, alert |
| `/health/full` | All dependencies: Postgres, Redis, external APIs | Rollback if > 2 failing |

The replication lag threshold of 500ms deserves explanation. Under normal conditions, Postgres streaming replication between US and EU runs at 80-120ms lag. During a schema migration, lag can spike to 2-5 seconds temporarily. The 500ms threshold is tight enough to catch broken replication but loose enough to tolerate brief migration-related spikes. If lag exceeds 500ms for more than 60 seconds, the deploy pauses and alerts the team.

### Step 5: Configure Data Residency Routing

The GDPR requirement means EU users' personal data must physically reside in the Frankfurt region. This is more than just running servers in Europe — the data routing logic needs to be baked into the application layer.

The implementation works through the entire user lifecycle:

- Users with EU billing addresses get `region=eu` assigned at signup
- API middleware reads the user's region from JWT claims on every request
- Write requests for EU users route to Frankfurt Postgres, regardless of which API server handles the request
- Read requests use the nearest replica automatically (performance optimization, no compliance issue since data exists in EU)

```typescript
// src/middleware/region-router.ts
const regionRouter = (req, res, next) => {
  const userRegion = req.jwt.claims.region;
  if (userRegion === 'eu') {
    req.dbClient = euPrimaryPool;  // Writes go to Frankfurt
  } else {
    req.dbClient = usPrimaryPool;  // Writes go to US East
  }
  next();
};
```

A migration script handles existing EU users: it moves their rows from the US Postgres to the EU instance, updates the routing table, and verifies data integrity with row-level checksums. The migration runs during a low-traffic window and takes about 20 minutes for 12,000 EU user records. Each batch is verified before the next starts — if a checksum doesn't match, the migration pauses rather than corrupting data.

## Real-World Example

Priya's team deploys the EU region first, migrates the German client's data to Frankfurt, and passes their compliance audit. The contract is signed — $180K ARR that was blocked on data residency.

Global p95 latency tells the performance story: EU users drop from 280ms to 45ms. Asian users drop from 340ms to 65ms. US users stay at 25ms (unchanged, since the primary is still in Virginia). The architecture survives a simulated region failure during a game day exercise — Cloudflare automatically routes EU traffic to US East within 30 seconds, and when Frankfurt recovers, traffic shifts back with no manual intervention.

The entire multi-region setup runs at $1,740/month on Hetzner. The same topology on AWS with managed RDS Multi-AZ, ElastiCache, and CloudFront would cost roughly $4,500/month. For a 15-person startup, that $2,760/month difference funds another engineer — or another year of runway.
