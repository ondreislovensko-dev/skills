---
title: "Diagnose Database Performance Bottlenecks with AI"
slug: diagnose-database-performance-bottlenecks
description: "Find and fix the slow queries killing your application's response times using AI-powered execution plan analysis."
skills: [sql-optimizer, data-analysis]
category: development
tags: [database, performance, postgresql, query-optimization, indexing]
---

# Diagnose Database Performance Bottlenecks with AI

## The Problem

Your application dashboard shows p95 latency spiking to 4 seconds. The APM tool points to the database, but you're staring at 200+ queries and a wall of `EXPLAIN` output that reads like assembly language. You know *something* is doing sequential scans, but figuring out which queries matter, what indexes to add without hurting write performance, and whether stale statistics are lying to the planner takes hours of expert-level analysis. Meanwhile, users are churning and the Slack channel is on fire.

Most teams don't have a dedicated DBA. The backend engineer who drew the short straw is googling "postgres explain analyze nested loop" at 10 PM trying to figure out if adding an index will fix the problem or create a new one. And the classic trap: adding an index that speeds up reads but silently degrades every INSERT and UPDATE until write latency becomes the next crisis.

## The Solution

Feed your slow query log and execution plans to the agent. It parses `EXPLAIN ANALYZE` output, identifies the root cause of each bottleneck, ranks them by impact, and generates exact `CREATE INDEX` statements and query rewrites -- complete with estimated performance improvements, write overhead calculations, and disk space requirements.

## Step-by-Step Walkthrough

### Step 1: Identify the Worst Offenders

```text
Here's our PostgreSQL slow query log from the last 24 hours (attached: slow-queries.log). Rank the top 5 queries by total time spent and show me how many times each was called.
```

Total time matters more than average time. A query averaging 68ms doesn't sound alarming -- until you see it ran 12,431 times yesterday:

| Rank | Query (abbreviated) | Total Time | Calls | Avg | Max |
|---|---|---|---|---|---|
| 1 | `SELECT * FROM events WHERE org_id = $1 AND created_at > $2 ORDER BY created_at DESC` | 847s | 12,431 | 68ms | 2,100ms |
| 2 | `SELECT u.*, COUNT(s.*) FROM users u LEFT JOIN sessions s ...` | 623s | 3,892 | 160ms | 4,300ms |
| 3 | `UPDATE subscriptions SET status = $1 WHERE expires_at < NOW() AND status = 'active'` | 412s | 288 | 1,430ms | 8,200ms |
| 4 | `SELECT DISTINCT tag FROM event_tags WHERE event_id IN (SELECT id FROM events WHERE org_id = $1)` | 389s | 8,201 | 47ms | 890ms |
| 5 | `SELECT * FROM audit_log WHERE actor_id = $1 ORDER BY created_at DESC LIMIT 50` | 201s | 5,440 | 37ms | 620ms |

Query #1 consumed 847 seconds of database time in a single day -- 14 minutes of pure computation, repeated constantly, for one query pattern. Query #3 only runs 288 times, but each execution locks the database for 1.4 seconds while scanning millions of rows. The max time of 8.2 seconds means it sometimes holds locks long enough to cause visible timeouts for other queries.

### Step 2: Analyze Execution Plans

```text
Run EXPLAIN ANALYZE on the top 3 queries using org_id = 'org_4f8a2c' and created_at > '2026-01-01'. Show me what's wrong with each.
```

Each query has a different root cause, and each requires a different fix:

**Query #1: events by org_id + created_at** -- The existing index on `org_id` alone forces PostgreSQL to fetch 84,000 rows matching the org, then sort them all in memory to satisfy `ORDER BY created_at DESC`. The sort step alone takes 40ms. A composite index that covers both the filter and the sort eliminates the in-memory sort entirely:

```sql
CREATE INDEX idx_events_org_created ON events (org_id, created_at DESC);
-- The DESC matters: it matches the ORDER BY direction, enabling a backward index scan
-- 68ms avg -> ~3ms (index-only scan + limit pushdown)
```

The column order in the composite index is critical. `(org_id, created_at DESC)` works because the query filters on `org_id` first (equality) then sorts on `created_at` (range). Reversing the order would force a full index scan on every query.

**Query #2: users with session count** -- A hash aggregate over a nested loop join. The sessions table has 12M rows, and the query scans per-user via index: 1,847 users times 6,500 average sessions = 12M index lookups. The planner chose a nested loop because it estimated fewer sessions per user than actually exist (stale statistics). Rewriting as a lateral join with pre-aggregation avoids the explosion:

```sql
SELECT u.*, s.session_count FROM users u
LEFT JOIN LATERAL (
  SELECT COUNT(*) as session_count FROM sessions WHERE user_id = u.id
) s ON true
WHERE u.org_id = 'org_4f8a2c';

-- Plus ensure the index exists:
-- CREATE INDEX idx_sessions_user_id ON sessions (user_id);
-- 160ms -> ~12ms
```

The `LATERAL` join tells PostgreSQL to compute the count per-user before joining, which maps perfectly to an index scan on `sessions(user_id)`. The nested loop join was trying to materialize all matching sessions first, then aggregate -- the wrong order of operations for this data shape.

**Query #3: batch subscription expiration** -- Sequential scan on 2.3M subscriptions, filtering by `expires_at` and `status`. Only ~5% of subscriptions are `active` at any given time, so a partial index is the perfect fit:

```sql
CREATE INDEX idx_subs_active_expiry ON subscriptions (expires_at)
    WHERE status = 'active';
-- Partial index covers only 115K active rows instead of 2.3M total
-- 1,430ms -> ~8ms
```

A full index on `(status, expires_at)` would also work, but it would be 20x larger because it includes all 2.3M rows. The partial index is 4MB instead of 80MB and scans faster because every entry in the index is relevant.

### Step 3: Validate Index Impact Before Production

```text
Estimate the total disk space and write overhead for these 3 new indexes. Are there any existing indexes that become redundant?
```

Adding indexes is never free. Every new index slows down writes, consumes disk, and needs vacuuming. Here is the full cost-benefit analysis:

| Index | Size | Write Impact | Notes |
|---|---|---|---|
| `idx_events_org_created` | ~680MB | +3% on INSERT | 34M rows, two columns |
| `idx_sessions_user_id` | -- | -- | **Already exists** as `idx_sessions_user` -- skip |
| `idx_subs_active_expiry` | ~4MB | negligible | Partial: only 115K active rows |

**Redundant index found:** `idx_events_org_id` (340MB) is fully superseded by the new composite index. The composite index handles every query the old single-column index could, plus the sort. Drop it after deploying the replacement.

**Net disk change:** +680MB + 4MB - 340MB = **+344MB** additional disk. The 3% write overhead on events INSERT is the only meaningful tradeoff -- one additional B-tree update per row. For the subscriptions partial index, write overhead is negligible because most INSERT/UPDATE operations touch rows with `status = 'pending'` or `'expired'`, which the partial index ignores entirely.

### Step 4: Generate the Migration Script

```text
Create a database migration file that adds the recommended indexes concurrently, drops the redundant one, and runs ANALYZE on affected tables.
```

The migration uses `CREATE INDEX CONCURRENTLY` so the table stays fully available during index creation -- no downtime, no locked writes. On a 34M-row table, the concurrent index build takes about 3-5 minutes but doesn't block any queries or transactions:

```sql
-- Step 1: Create new indexes without blocking writes
CREATE INDEX CONCURRENTLY idx_events_org_created
  ON events (org_id, created_at DESC);

CREATE INDEX CONCURRENTLY idx_subs_active_expiry
  ON subscriptions (expires_at) WHERE status = 'active';

-- Step 2: Verify new indexes are valid (CONCURRENTLY can fail silently)
SELECT indexname, indexdef FROM pg_indexes
  WHERE indexname IN ('idx_events_org_created', 'idx_subs_active_expiry');

-- Step 3: Drop redundant index only after new one is confirmed
DROP INDEX CONCURRENTLY idx_events_org_id;

-- Step 4: Update planner statistics for affected tables
ANALYZE events;
ANALYZE subscriptions;
```

The `ANALYZE` at the end is essential. Without it, the query planner might continue using old statistics and choose suboptimal plans even with the new indexes available. This is especially important for the sessions table, which had stale statistics from a bulk import.

## Real-World Example

A backend engineer at a 15-person marketplace startup noticed checkout completion rates dropped 12% over the past month. Their APM showed database response times increased from 45ms (p50) to 380ms (p50). The team had no dedicated DBA and nobody had changed the schema recently -- the degradation was gradual, caused by data growth outpacing the existing index strategy.

They fed the agent their `pg_stat_statements` output sorted by total_time. Four queries were responsible for 78% of total database time. `EXPLAIN ANALYZE` revealed two missing composite indexes, one query that needed a rewrite from a correlated subquery to a JOIN, and stale statistics on a table that received a 2M-row bulk import the previous week without a follow-up `ANALYZE`.

The generated migration added 2 indexes concurrently, rewrote the subquery, and ran `ANALYZE` on three tables. After deployment, p50 latency dropped from 380ms to 28ms, and checkout completion rates recovered to their previous levels within 48 hours. Total time from diagnosis to merged migration PR: 35 minutes. The indexes have been stable for three months with no measurable impact on write performance.
