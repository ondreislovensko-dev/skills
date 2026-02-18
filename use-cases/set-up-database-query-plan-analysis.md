---
title: "Set Up Automated Database Query Plan Analysis with AI"
slug: set-up-database-query-plan-analysis
description: "Automatically capture, analyze, and optimize slow database query execution plans using AI agents."
skills: [sql-optimizer, data-analysis, report-generator]
category: development
tags: [database, sql, query-plans, performance, optimization]
---

# Set Up Automated Database Query Plan Analysis with AI

## The Problem

Ravi's application is getting slower and nobody knows which queries are responsible. The DBA runs `EXPLAIN ANALYZE` on a few suspects, stares at nested loop joins and sequential scans, and recommends an index. But there are hundreds of queries in the codebase. Execution plans change as data grows. What was fast last month is a bottleneck today -- the `orders` table crossed 8 million rows and a query that used to return in 50ms now takes over a second.

Manual query plan review does not scale. And most developers cannot read execution plans fluently. The output looks like an accounting spreadsheet written in a foreign language -- nested parentheses, cost estimates, row counts that may or may not match reality -- so performance issues pile up until the ops team starts getting paged about database CPU at 85%.

## The Solution

Using the **sql-optimizer**, **data-analysis**, and **report-generator** skills, this walkthrough parses slow query logs to find the worst offenders, runs `EXPLAIN ANALYZE` to diagnose the root cause of each one, and generates a migration file with the exact indexes and fixes that solve the problems.

## Step-by-Step Walkthrough

### Step 1: Find the Worst Offenders

The PostgreSQL slow query log has the raw data. The first step is to turn it from a 500 MB text file into an actionable list:

```text
Parse the PostgreSQL slow query log at /var/log/postgresql/slow.log. Extract all queries that took longer than 500ms in the past 7 days. Group by query pattern and show frequency and average duration.
```

The top 3 patterns account for 73% of total slow query time:

| Pattern | Count | Avg Duration | Max Duration | Total Time |
|---------|-------|-------------|-------------|------------|
| `SELECT * FROM orders JOIN line_items...` | 3,412 | 1,240ms | 8,430ms | 4,231s |
| `SELECT COUNT(*) FROM events WHERE...` | 8,901 | 780ms | 3,210ms | 6,942s |
| `UPDATE users SET last_seen_at...` | 12,340 | 520ms | 1,890ms | 6,416s |

The orders JOIN runs 3,400 times a week at 1.2 seconds each. That is 70 minutes of database time spent on a single query pattern -- and every one of those executions is a user waiting for a page to load. The events COUNT runs almost 9,000 times but each call is faster -- still, the sheer volume makes it the biggest total time consumer at nearly 2 hours of cumulative database time per week.

The 47 remaining slow query patterns together account for only 27% of total slow time. Fixing just the top 3 would give the biggest return.

### Step 2: Diagnose Each Query

Now for the part most developers skip because execution plans are hard to read:

```text
Run EXPLAIN ANALYZE on the top 3 slow query patterns and tell me exactly what's wrong with each one.
```

**Query 1: The orders JOIN**

```sql
SELECT * FROM orders JOIN line_items ON orders.id = line_items.order_id
WHERE orders.created_at > '2025-01-01' AND orders.status = 'pending'
```

The execution plan reveals the core problem: a nested loop join on `line_items` driven by a sequential scan on `orders`. The planner estimates 500 matching rows, but 34,210 rows actually match -- a 68x underestimate. With only 500 expected rows, a nested loop makes sense (look up each matching line item individually). With 34,000, it is catastrophic -- 34,000 individual index lookups instead of a single hash join.

**Root cause:** Table statistics are stale. The planner is making decisions based on data distribution from months ago. It thinks "pending" orders are rare (they used to be), but a recent product change -- allowing orders to sit in "pending" for 7 days instead of auto-canceling after 24 hours -- means 34,000 orders are now sitting in "pending" status. The planner has not been told about this shift in data distribution.

This is a common and insidious pattern: a business logic change causes a data distribution change, which causes the query planner to choose a different (worse) execution plan. The code did not change, the schema did not change, but query performance degraded dramatically.

**Query 2: The events COUNT**

```sql
SELECT COUNT(*) FROM events
WHERE event_type = 'page_view' AND created_at > '2026-01-01'
```

The `events` table has 12 million rows, and every COUNT query does a full sequential scan because there is no index on the filtered columns. The query filters by `event_type` and `created_at`, but neither column is indexed. PostgreSQL has no choice but to read every single row and check the filter conditions. At 12 million rows, that takes 780ms on average. This query powers the analytics dashboard, which refreshes every 30 seconds -- so it runs constantly.

**Query 3: The users UPDATE**

This one is counterintuitive. The `last_seen_at` update touches a column that has an index on it. Every UPDATE rewrites the index entry -- PostgreSQL must delete the old entry and insert a new one. With 12,340 updates per week, the index maintenance overhead is the bottleneck -- not the query logic itself. The index on `last_seen_at` was probably added for a read query that no longer exists.

### Step 3: Apply the Fixes

Each query has a different root cause and a different fix. That is important -- "add an index" is not always the answer.

**Fix 1:** Update statistics and add a composite index:

```sql
-- Refresh statistics so the planner sees current data distribution
ANALYZE orders;

-- Composite index matches the WHERE clause column order
CREATE INDEX idx_orders_status_created ON orders(status, created_at);
```

Expected improvement: 1,240ms down to approximately 45ms. The composite index lets the planner use an index scan instead of a sequential scan, and fresh statistics ensure it chooses a hash join instead of a nested loop. The column order in the index matters -- `status` first (equality check) followed by `created_at` (range scan) is optimal for this query pattern.

**Fix 2:** Add an index for the events COUNT:

```sql
CREATE INDEX idx_events_type_created ON events(event_type, created_at);
```

Expected improvement: 780ms down to approximately 35ms. The index turns a 12-million-row sequential scan into an index range scan that reads only the matching rows.

**Fix 3:** Remove the unnecessary index on `last_seen_at`:

```sql
-- This index is never used for reads but slows down every write
DROP INDEX idx_users_last_seen_at;
```

Expected improvement: 520ms down to approximately 15ms. Dropping the index eliminates the write amplification on every update. If a read query later needs to filter or sort by `last_seen_at`, it can be added back as a partial index (e.g., `WHERE last_seen_at > now() - interval '7 days'`) that covers recent lookups without penalizing the constant stream of writes.

This is a good reminder that indexes are not free. Every index speeds up reads but slows down writes. On a column that gets updated 12,000 times a week and queried rarely, the index costs more than it provides.

### Step 4: Generate the Migration and Report

```text
Create a query optimization report with all findings, recommended indexes, and estimated impact. Format it as a markdown document I can share with the team.
```

The report includes before/after execution plans for each query, the SQL statements for each fix, and a priority ranking based on total database time saved:

| Fix | Query Pattern | Current Duration | Expected Duration | Weekly Time Saved |
|-----|--------------|-----------------|-------------------|-------------------|
| Composite index on orders | orders JOIN | 1,240ms | ~45ms | 68 minutes |
| Index on events | events COUNT | 780ms | ~35ms | 110 minutes |
| Drop last_seen_at index | users UPDATE | 520ms | ~15ms | 104 minutes |

The migration file is idempotent -- each `CREATE INDEX` uses `IF NOT EXISTS` and each `DROP INDEX` uses `IF EXISTS`, so it can be safely re-run without errors. The team can review the report in sprint planning and apply the migration with confidence, knowing exactly what each change does and why.

## Real-World Example

Ravi applies the migration on a Tuesday morning. The results are immediate and dramatic: average API response time drops from 340ms to 95ms. Database CPU falls from 85% during business hours to 40%. The orders JOIN that was taking 1.2 seconds now returns in 40ms -- a 30x improvement from two lines of SQL.

The biggest surprise is the third fix. Dropping the `last_seen_at` index -- removing something rather than adding it -- cuts 500ms off a query that runs 12,000 times a week. Not every performance problem is a missing index. Sometimes the index itself is the problem.

Ravi schedules a monthly re-run of the slow query analysis. As the database grows from 80 GB toward 200 GB, new bottlenecks will emerge. Query patterns that are fast today may not be fast at 3x the data volume -- statistics go stale, data distributions shift, and the planner makes different choices. Catching them in a monthly review beats catching them at 3 AM when the pager goes off.

He also adds `ANALYZE` to the nightly maintenance window so table statistics stay fresh automatically. The orders JOIN disaster happened because a business logic change altered the data distribution, and stale statistics caused the planner to pick the wrong execution plan. With nightly `ANALYZE`, the planner always has current information -- and that particular class of regression cannot repeat.
