---
title: "Automate Data Migration Between Databases"
slug: automate-database-migration
description: "Build an automated pipeline to migrate data between databases with schema mapping, validation, and zero-downtime cutover."
skills: [data-migration, sql-optimizer]
category: development
tags: [database, migration, etl, data-pipeline, schema]
---

# Automate Data Migration Between Databases

## The Problem

Marcus runs a mid-size e-commerce platform on MySQL 5.7. The database has served them well for five years, but the team keeps hitting walls — no native JSON operations, limited window function support, and replication lag that spikes during holiday sales. They have decided to move to PostgreSQL 16. The problem is 45 tables, 12 million rows, and a codebase full of MySQL-specific quirks: `TINYINT(1)` booleans, `ENUM` types everywhere, `DATETIME` columns with no timezone awareness, and column names from the original developer's questionable naming conventions (`cust_name`, `ord_date`, `ord_status`).

The last time someone tried a "quick migration" on a staging copy, it failed halfway through because the script tried to insert `order_items` before `orders` existed. Foreign keys mean the migration order matters — get it wrong and every row fails with a constraint violation. And that is just one of a dozen things that can go wrong: data type mismatches, encoding issues, null handling differences between MySQL and PostgreSQL, and timezone conversions that silently corrupt timestamps.

The app serves real customers, so extended downtime is not an option. Marcus needs the migration to happen in the background, with validation proving nothing was lost, and a cutover window measured in minutes.

## The Solution

Using the **data-migration** and **sql-optimizer** skills, the agent builds a repeatable migration pipeline: maps every column between schemas, resolves foreign key dependencies automatically, transforms data types in flight, and validates the result row by row. The whole thing is resumable — if it fails at batch 400 of 800, it picks up where it left off instead of starting over.

## Step-by-Step Walkthrough

### Step 1: Map the Source and Target Schemas

Marcus describes the current MySQL setup and what he wants in PostgreSQL. The schema analysis identifies 45 tables: 38 map directly, 7 need transformation.

```text
I'm migrating from a legacy MySQL 5.7 database to PostgreSQL 16.
Source has 45 tables, ~12M rows total. The big tables are orders (4M rows),
order_items (8M rows), and customers (500K rows). Some columns need renaming,
some ENUM types need converting, and DATETIME columns need timezone handling.
Generate the schema mapping.
```

The type conversion map covers every incompatibility between MySQL and PostgreSQL:

| MySQL Type | PostgreSQL Type | Columns Affected |
|---|---|---|
| `TINYINT(1)` | `BOOLEAN` | 12 columns across 8 tables |
| `ENUM('active','inactive')` | `VARCHAR` + `CHECK` constraint | 5 columns |
| `DATETIME` | `TIMESTAMPTZ` | 34 columns |
| `INT AUTO_INCREMENT` | `SERIAL` / `BIGSERIAL` | All primary keys |
| `DOUBLE` | `DOUBLE PRECISION` | 7 columns |
| `TEXT` (latin1) | `TEXT` (re-encoded to UTF-8) | 3 columns |

Column renames clean up the legacy naming conventions. Nobody wants to type `cust_name` for the next five years:

- `customers.cust_name` becomes `customers.name`
- `orders.ord_date` becomes `orders.created_at`
- `orders.ord_status` becomes `orders.status`

Two files come out of this step: `migration/schema-map.json` with the full column-by-column mapping for every table, and `migration/create-target-schema.sql` with the PostgreSQL DDL ready to execute.

### Step 2: Build the Migration Pipeline with Dependency Ordering

Foreign keys dictate the migration order. You cannot insert `order_items` before `orders` exist, and you cannot insert `orders` before `customers` exist. A topological sort on the FK graph produces 6 dependency levels — tables at the same level can be migrated in parallel.

```text
Build the migration script. Tables have foreign keys so order matters.
I need: dependency resolution, batch processing for large tables,
and the ability to resume if it fails midway.
```

The pipeline comes as five files:

- **`migration/migrate.ts`** — main orchestrator that drives the migration in FK-dependency order
- **`migration/dependency-graph.ts`** — FK-based topological sort, handles circular references by identifying which FK to defer
- **`migration/batch-reader.ts`** — cursor-based batch reading that does not hold the entire table in memory
- **`migration/transform.ts`** — per-table transformation functions for type conversions and renames
- **`migration/state.ts`** — checkpoint tracking for resume capability

Small tables under 10K rows get a single `INSERT ... SELECT`. Large tables process in batches of 5,000 with cursor pagination — `orders` (4M rows) takes roughly 800 batches over 12 minutes, `order_items` (8M rows) takes 1,600 batches over 25 minutes. After every batch, a checkpoint file records `{ table, lastId, rowsMigrated }`. If the script crashes at batch 600, restarting it skips all completed tables and resumes from the last checkpoint. No duplicate data, no lost progress.

### Step 3: Handle Data Transformations

The interesting part is the customers table. MySQL stores address data across 5 separate columns; PostgreSQL gets a single `JSONB` column. And phone numbers are a mess — some have dashes, some have country codes, some have neither, and a few have letters mixed in from when the field was used for fax numbers in 2019.

```text
The customers table has address data split across 5 columns in MySQL.
In PostgreSQL, I want it in a JSONB column. Also, phone numbers are stored
inconsistently — some have dashes, some have country codes, some don't.
Normalize during migration.
```

Address consolidation collapses `street`, `city`, `state`, `zip`, and `country` into a single `address` JSONB field. If all five source fields are null, the result is `null` — not an empty object. This matters for queries: `WHERE address IS NULL` should find customers with no address, not customers with `{}`.

Phone normalization runs a four-step pipeline:

1. Strip all non-numeric characters
2. If 10 digits, prepend `+1` (US default)
3. If 11 digits starting with `1`, prepend `+`
4. If no pattern matches, keep the original and flag for manual review

About 2% of records hit step 4 and get written to `migration/review/phones-to-check.csv` for manual inspection. Better to flag 10,000 records for human review than silently mangle them with a guess.

### Step 4: Validate the Migration

Trust but verify. The validation suite runs six checks after migration completes:

```text
After migration, validate that all data transferred correctly.
Check row counts, spot-check random records, verify foreign key integrity,
and compare aggregates (sum of order totals, count of active customers).
```

- **Row counts** — source vs. target for all 45 tables. Any mismatch is a hard failure.
- **Random sample** — 100 random records per table, field-by-field comparison after transformation. Catches subtle type conversion bugs.
- **Foreign key integrity** — every FK reference resolves, no orphaned records. A single broken FK means a batch was migrated out of order.
- **Aggregates** — `SUM(orders.total)`, `COUNT(customers WHERE status='active')`, `COUNT(DISTINCT order_items.product_id)` compared between source and target. These catch rounding errors and filter bugs.
- **Null check** — no unexpected `NULL`s in `NOT NULL` columns
- **Encoding** — sample `TEXT` fields for UTF-8 validity, catching latin1 characters that did not convert cleanly

Results go to `migration/validation-report.json` with pass/fail per check. The full suite runs in about 3 minutes. Marcus runs it once on staging, fixes the two edge cases it catches, and runs it again to confirm.

### Step 5: Plan Zero-Downtime Cutover

The app serves real customers all day, every day. The cutover window needs to be measured in minutes, not hours.

```text
Plan the cutover strategy. I need minimal downtime — the app serves
real customers. Can we do it with less than 5 minutes of downtime?
```

**Phase 1 (zero downtime):** Run the full migration to PostgreSQL in the background while the app keeps serving traffic from MySQL. This takes about 40 minutes. Set up logical replication from MySQL to capture any writes that happen during migration. Validate the migrated data.

**Phase 2 (zero downtime):** Apply the accumulated changes from the replication log — all the orders placed and customers updated while the migration was running. Re-validate the affected tables.

**Phase 3 (2-3 minutes of downtime):** Set the app to maintenance mode. Apply the final delta — should be under 1,000 rows. Switch the application database config to PostgreSQL. Run a quick validation (row counts plus the latest 100 orders to verify freshness). Remove maintenance mode.

The rollback plan is straightforward: if validation fails at any point during Phase 3, revert the config to MySQL and exit maintenance mode. MySQL is untouched throughout the entire process — it is always the fallback. The worst case is 3 minutes of maintenance mode followed by "never mind, we're reverting."

## Real-World Example

Marcus runs the migration on staging twice to build confidence, fixing a timezone conversion edge case on the second run. He schedules the production cutover for Saturday night when traffic is lowest.

The full migration takes 38 minutes in the background while the app keeps serving traffic. The replication log captures 1,200 changes made during that window. Phase 3 takes 2 minutes and 40 seconds — the final delta is just 89 rows.

Validation passes clean: all row counts match, aggregates align within 0.01% (the difference is a rounding change in one decimal column, which is expected), and the 100-record spot check finds zero discrepancies. The phone normalization flagged 340 records for manual review, but none of them were data loss — just formatting inconsistencies the team resolves Monday morning.

The legacy MySQL instance stays archived for 90 days, just in case. Nobody needs it. The PostgreSQL queries that used to require application-level workarounds — CTEs, window functions, JSON operations — now run as straightforward SQL. And the team stops dreading the next holiday traffic spike, because PostgreSQL's replication does not have MySQL's lag problem.
