---
title: "Automate Incident Response Runbooks with AI"
slug: automate-incident-response-runbooks
description: "Generate, maintain, and execute structured runbooks that guide on-call engineers through common production incidents."
skills: [coding-agent, markdown-writer, docker-helper]
category: devops
tags: [incident-response, runbooks, on-call, operations, reliability]
---

# Automate Incident Response Runbooks with AI

## The Problem

Your on-call rotation is a trial by fire. When a new engineer gets paged at 2 AM about a database connection spike, they have no playbook to follow. The senior engineer who handled this last time fixed it from memory and never documented the steps. Your team has a wiki page called "Incident Procedures" with three outdated entries from 2024 that reference infrastructure you have since migrated. Every incident relies on tribal knowledge locked in the heads of two senior engineers, and when they are on vacation, mean time to resolution doubles.

## The Solution

Use the **coding-agent** to analyze past incidents and generate executable runbooks, **markdown-writer** to format them into clear step-by-step procedures, and **docker-helper** to create diagnostic scripts that runbooks can reference.

```bash
npx terminal-skills install coding-agent markdown-writer docker-helper
```

## Step-by-Step Walkthrough

### 1. Feed the agent your incident history

```
Here are our last 20 incident reports from PagerDuty (incidents-export.json)
and our post-incident Slack threads (exported as text files in incidents/ folder).
Analyze common patterns and generate runbooks for the most frequent incident types.
Our stack: Kubernetes on AWS, Postgres, Redis, Express API services.
```

### 2. The agent identifies incident categories

```
Incident Pattern Analysis (20 incidents, last 6 months):

Category                    | Count | Avg Resolution | Has Runbook?
----------------------------|-------|----------------|-------------
Database connection exhaustion | 5  | 34 min         | No
Memory/OOM kills on pods      | 4  | 22 min         | No
Redis connection timeouts      | 3  | 18 min         | No
Certificate expiration         | 3  | 45 min         | No
Deployment rollback needed     | 3  | 28 min         | No
External API degradation       | 2  | 52 min         | No

Recommendation: Generate runbooks for top 5 categories.
These cover 90% of your incidents.
```

### 3. The agent generates detailed runbooks

```
Generated runbook: runbooks/db-connection-exhaustion.md

# Database Connection Exhaustion

**Severity:** P1 | **On-call team:** Backend | **Expected resolution:** < 15 min

## Symptoms
- Alert: "Postgres connection pool utilization > 90%"
- API responses slow (> 2s) or returning 503
- Grafana dashboard: DB Connections panel shows flat line at max

## Diagnosis Steps

### Step 1: Check current connections
    kubectl exec -it deploy/api -n production -- \
      node -e "const pool = require('./db'); pool.query('SELECT count(*) FROM pg_stat_activity')"

    Expected: < 100 connections normal, > 180 is critical (max_connections=200)

### Step 2: Identify connection consumers
    kubectl exec -it deploy/postgres-0 -n database -- psql -U app -c \
      "SELECT application_name, state, count(*) FROM pg_stat_activity GROUP BY 1,2 ORDER BY 3 DESC"

### Step 3: Check for long-running queries
    kubectl exec -it deploy/postgres-0 -n database -- psql -U app -c \
      "SELECT pid, now() - pg_stat_activity.query_start AS duration, query
       FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC LIMIT 5"

## Resolution

### If long-running query is the cause:
    kubectl exec -it deploy/postgres-0 -n database -- psql -U app -c \
      "SELECT pg_terminate_backend(<PID>)"

### If a specific service is leaking connections:
    kubectl rollout restart deploy/<service-name> -n production

### If pool size needs temporary increase:
    kubectl set env deploy/api -n production DB_POOL_MAX=50
```

### 4. The agent creates diagnostic scripts

```
Generated diagnostic toolkit:

scripts/
├── diagnose-db.sh         # Connection stats, slow queries, lock contention
├── diagnose-memory.sh     # Pod memory usage, OOM history, heap snapshots
├── diagnose-redis.sh      # Connection count, memory usage, slow log
├── diagnose-network.sh    # DNS resolution, inter-pod latency, cert expiry
└── rollback-deploy.sh     # Safe deployment rollback with health checks

Each script:
- Requires only kubectl access (no SSH needed)
- Outputs structured results with severity indicators
- Includes "escalation needed" thresholds
- Works from any engineer's laptop
```

### 5. The agent sets up runbook maintenance automation

```
Created .github/workflows/runbook-validation.yml:

On every infrastructure PR:
- Checks referenced kubectl commands against current cluster resources
- Validates referenced Grafana dashboard UIDs still exist
- Flags runbooks not updated in > 90 days
- Generates PR comment if a changed service has a related runbook

Runbook index page: runbooks/README.md
- Links all runbooks with last-updated dates
- Quick reference table: alert name → runbook link
- On-call cheat sheet with escalation contacts
```

## Real-World Example

Kai is an SRE manager at a 30-person engineering team. Three new engineers joined the on-call rotation last quarter, and mean time to resolution spiked from 20 minutes to 48 minutes because they lacked the institutional knowledge to diagnose common issues.

1. Kai exports six months of incident data and post-incident Slack threads
2. The agent identifies five recurring incident patterns covering 90% of all pages
3. It generates detailed runbooks with exact diagnostic commands, decision trees, and resolution steps — all tested against the current cluster configuration
4. The agent creates a diagnostic script toolkit that any on-call engineer can run from their laptop
5. After deploying the runbooks, new engineers resolve incidents at the same speed as seniors, and mean time to resolution drops back to 19 minutes within one month

## Related Skills

- [coding-agent](../skills/coding-agent/) -- Analyzes incident patterns and generates diagnostic scripts
- [markdown-writer](../skills/markdown-writer/) -- Formats runbooks into clear, actionable procedures
- [docker-helper](../skills/docker-helper/) -- Creates container diagnostic and remediation tooling
