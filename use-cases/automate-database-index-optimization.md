---
title: "Set Up Automated Database Index Optimization"
slug: automate-database-index-optimization
description: "Analyze query patterns, identify missing indexes, remove unused ones, and keep your database performant as data grows."
skills: [sql-optimizer, data-analysis, report-generator]
category: development
tags: [database, indexes, postgresql, performance, optimization]
---

# Set Up Automated Database Index Optimization

## The Problem

Your PostgreSQL database started fast. Now, 18 months and 12 million rows later, the dashboard takes 8 seconds to load. The orders listing page triggers a sequential scan on a 4-million-row table. Three API endpoints regularly timeout during peak hours.

Your team has added indexes reactively — someone complains about a slow page, a senior engineer adds an index, the page gets faster. But nobody tracks the full picture. You have 67 indexes across 24 tables. Some were added for queries that no longer exist. Others duplicate each other. Meanwhile, the 5 queries responsible for 80% of your database load have no covering indexes at all.

Index bloat slows down writes. Missing indexes slow down reads. Without systematic analysis, you are guessing — and every guess costs either read performance or write performance.

## The Solution

Use **sql-optimizer** to analyze query plans and recommend index changes, **data-analysis** to identify patterns in slow query logs, and **report-generator** to produce actionable optimization reports.

## Step-by-Step Walkthrough

### Step 1: Audit Current Index Usage

```text
Analyze our PostgreSQL database indexes. Show which are used, which are unused, which are duplicates, and the overall index bloat.
```

The audit examines all 67 indexes and reveals how much of the indexing strategy is dead weight:

**Unused indexes (no scans in 30 days): 12**

These indexes exist on disk, slow down every INSERT, UPDATE, and DELETE, but no query has touched them in a month:

| Index | Size | Notes |
|---|---|---|
| `idx_orders_legacy_status` | 284 MB | From the old order status system, removed 6 months ago |
| `idx_users_old_email_lower` | 156 MB | Superseded by the citext column migration |
| `idx_invoices_draft_flag` | 89 MB | The "draft" feature was removed in v2.3 |
| ... 9 more | 1.27 GB total | |

**Duplicate/overlapping indexes: 4 pairs**

- `idx_orders_user_id` is a strict subset of `idx_orders_user_id_created_at` — the composite index handles every query the single-column index does
- `idx_products_name` and `idx_products_name_lower` are redundant because the column was migrated to `citext`, which is case-insensitive by default

**Bloated indexes (more than 40% dead tuples): 3**

- `idx_events_created_at` — 62% bloat, consuming 1.2 GB when it should be 456 MB
- `idx_sessions_token` — 48% bloat

**Total wasted space: 1.8 GB** across unused and bloated indexes. The orders table alone has 8 indexes, and the write overhead is estimated at 15% — every new order pays an insert tax for indexes that serve no purpose.

### Step 2: Identify Missing Indexes from Slow Queries

```text
Analyze the slow query log from the past 7 days. Find the top queries that would benefit from new indexes.
```

The slow query log contains 1,247 queries that exceeded 500ms in the past week. The top three account for the majority of the pain:

**Query 1: The orders listing page**

```sql
SELECT * FROM orders
WHERE user_id = $1 AND status = 'active'
ORDER BY created_at DESC;
-- Avg: 2,340ms | 892 calls/day | Sequential scan on 4.1M rows
```

This query runs almost 900 times per day and scans the entire 4.1-million-row orders table every time. A composite index on `(user_id, status, created_at DESC)` turns the sequential scan into an index-only scan:

```sql
CREATE INDEX idx_orders_user_status_created
  ON orders(user_id, status, created_at DESC);
```

**Query 2: The analytics event counter**

```sql
SELECT count(*) FROM events
WHERE org_id = $1 AND type = $2 AND created_at > $3;
-- Avg: 1,890ms | 340 calls/day | Partial index scan
```

A partial index covering only the event types that get queried cuts the index size dramatically:

```sql
CREATE INDEX idx_events_org_type_created
  ON events(org_id, type, created_at)
  WHERE type IN ('click', 'view', 'purchase');
```

**Query 3: The login lookup**

```sql
SELECT * FROM users WHERE lower(email) = $1;
-- Avg: 980ms | 2,100 calls/day | Sequential scan
```

Every login attempts a case-insensitive email lookup by computing `lower()` on every row. A functional index pre-computes the lowercase value:

```sql
CREATE INDEX idx_users_email_lower ON users(lower(email));
```

**Projected improvement:** 87% reduction in total slow query time across all three queries.

### Step 3: Generate and Validate the Migration

```text
Create a migration that drops unused indexes and adds recommended ones. Include rollback steps and estimated lock times.
```

The migration uses `CONCURRENTLY` for every operation — no table locks, no downtime:

```sql
-- 20260217_optimize_indexes.sql

-- Phase 1: Drop unused indexes (instant, no locks)
DROP INDEX CONCURRENTLY IF EXISTS idx_orders_legacy_status;
DROP INDEX CONCURRENTLY IF EXISTS idx_users_old_email_lower;
DROP INDEX CONCURRENTLY IF EXISTS idx_invoices_draft_flag;
-- ... 9 more drops, freeing 1.8 GB

-- Phase 2: Add missing indexes (concurrent build, no downtime)
CREATE INDEX CONCURRENTLY idx_orders_user_status_created
  ON orders(user_id, status, created_at DESC);
-- Estimated build time: ~45 seconds on 4.1M rows

CREATE INDEX CONCURRENTLY idx_events_org_type_created
  ON events(org_id, type, created_at)
  WHERE type IN ('click', 'view', 'purchase');

CREATE INDEX CONCURRENTLY idx_users_email_lower
  ON users(lower(email));

-- Phase 3: Reindex bloated indexes
REINDEX INDEX CONCURRENTLY idx_events_created_at;
-- Reclaims ~744 MB (from 1.2 GB to 456 MB)
```

A rollback script accompanies the migration — it drops the new indexes and recreates the old ones, in case any query depends on the old index structure in unexpected ways. Total estimated execution: 3-5 minutes, zero downtime.

### Step 4: Set Up Weekly Index Health Monitoring

```text
Create a weekly report that tracks index usage, identifies new slow queries, and recommends adjustments.
```

A scheduled report runs every Monday at 6:00 AM and covers five areas:

1. **Index usage stats** — scan counts, rows read, cache hit ratio for every index
2. **Newly unused indexes** — any index with zero scans in the past 14 days gets flagged
3. **New slow queries** — queries exceeding 500ms that are not covered by existing indexes
4. **Index bloat progression** — tracks dead tuple percentage over time, recommends reindex when bloat exceeds 50%
5. **Write performance impact** — indexes per high-write table, estimated insert overhead

The report lands as markdown in `docs/db-reports/` and triggers a Slack notification. If any index exceeds 50% bloat or any new query averages over 2 seconds, the notification tags the database on-call engineer.

This turns index management from a reactive firefight into a weekly 5-minute review. The database does not quietly degrade for months until someone notices the dashboard is slow.

## Real-World Example

Kofi, a backend engineer at a 20-person e-commerce SaaS, was firefighting performance issues weekly. The orders table had grown to 4 million rows, and the main listing endpoint was timing out for large accounts. The team had added indexes over 18 months without a strategy — 8 indexes on the orders table alone, some for features that had been removed a year ago.

He ran the three-skill workflow during a Friday maintenance window. The audit found 12 unused indexes consuming 1.8 GB and 4 duplicate pairs. More importantly, it identified that the top 3 slow queries — responsible for 73% of all timeouts — had no proper covering indexes. The migration dropped dead weight, added 3 targeted indexes, and reindexed 2 bloated ones. Total execution: 4 minutes with zero downtime.

The results were immediate. The orders listing endpoint dropped from 2,340ms to 180ms — a 13x improvement. Weekly slow query volume fell from 1,247 to 94. Write performance on the orders table improved 12% from removing 5 unnecessary indexes. And the Monday reports now catch new slow queries within a week of them appearing, before they become customer-facing issues.

The database that was heading toward a crisis at the current growth rate now has headroom for another 18 months of data accumulation — without any schema changes or hardware upgrades.
