---
title: "Set Up a Real-Time Analytics Dashboard from Scratch"
slug: set-up-realtime-analytics-dashboard
description: "Build a live analytics dashboard that ingests event streams, aggregates metrics, and renders updating charts — without relying on expensive third-party platforms."
skills: [realtime-analytics, data-analysis, docker-helper]
category: data-ai
tags: [analytics, real-time, dashboard, event-streaming, clickhouse]
---

# Set Up a Real-Time Analytics Dashboard from Scratch

## The Problem

Your product team wants a live dashboard showing active users, conversion funnels, and feature adoption — updated every few seconds, not every 24 hours. Third-party analytics tools cost thousands per month at your event volume, and self-hosted options like Matomo are not truly real-time. You need a custom pipeline: ingest events, aggregate them on the fly, and render live charts.

## The Solution

Wire together an event ingestion API, a columnar database optimized for analytics queries (ClickHouse), and a lightweight frontend that polls aggregated data. Three skills handle each layer: **realtime-analytics** for the pipeline architecture, **data-analysis** for the aggregation queries, and **docker-helper** for containerizing the whole stack.

## Step-by-Step Walkthrough

### Step 1: Design the Event Schema

```text
Design an analytics event schema for a SaaS product. Events include page_view,
button_click, signup_started, signup_completed, feature_used, and error_occurred.
Each event needs: event_name, timestamp, session_id, user_id (nullable for
anonymous), device_type, country_code, and a properties JSON column for
event-specific data. Output a ClickHouse CREATE TABLE statement optimized
for time-range queries.
```

ClickHouse is the right tool here because analytics queries are almost always "aggregate a huge number of rows filtered by time range." It's columnar storage — reading one column across a million rows is orders of magnitude faster than row-based databases.

The schema uses `LowCardinality` for columns with few distinct values (event names, device types, country codes) which gives ClickHouse massive compression wins:

```sql
CREATE TABLE events (
    event_name   LowCardinality(String),
    timestamp    DateTime64(3),
    session_id   String,
    user_id      Nullable(String),
    device_type  LowCardinality(String),
    country_code LowCardinality(FixedString(2)),
    properties   String,  -- JSON stored as string, extracted at query time
    date         Date DEFAULT toDate(timestamp)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (event_name, timestamp)
TTL date + INTERVAL 90 DAY;
```

Partitioning by month keeps queries fast — a "last 24 hours" query only reads the current partition. The 90-day TTL automatically cleans up old data without manual intervention.

### Step 2: Build the Ingestion Endpoint

```text
Create a Node.js ingestion service in src/ingest/ that accepts POST /events
with a JSON array of up to 500 events. Validate each event against the schema.
Batch-insert into ClickHouse every 2 seconds or when the buffer reaches 1000
events, whichever comes first. Add a health check at GET /health that returns
buffer size and last flush time.
```

The ingestion service accepts batches of up to 500 events per request. Events are validated against the schema (rejecting malformed data before it enters the pipeline) and buffered in memory. The buffer flushes to ClickHouse on whichever trigger comes first: 2 seconds elapsed or 1,000 events accumulated.

This batching strategy is critical for ClickHouse performance. Individual row inserts are expensive — ClickHouse is designed for bulk operations. Buffering and flushing in batches of 1,000 keeps write performance high even under heavy event volume.

The health check at `GET /health` returns the current buffer size and last flush timestamp. If the buffer is growing but not flushing, something is wrong with the ClickHouse connection — monitoring catches it before events start dropping.

### Step 3: Create Aggregation Queries

```text
Write ClickHouse SQL queries for these dashboard panels:
1. Active users in the last 5 minutes (count distinct session_id)
2. Signup funnel: signup_started -> signup_completed, grouped by hour for the last 24h
3. Top 10 features used today, ranked by unique users
4. Error rate per minute for the last hour
Return each query as a named .sql file in src/queries/.
```

Four queries power the four dashboard panels. Here's the signup funnel — the most interesting one because it uses ClickHouse's window functions to compute conversion rates:

```sql
-- src/queries/signup_funnel.sql
SELECT
    toStartOfHour(timestamp) AS hour,
    countIf(event_name = 'signup_started') AS started,
    countIf(event_name = 'signup_completed') AS completed,
    round(completed / started * 100, 1) AS conversion_pct
FROM events
WHERE timestamp > now() - INTERVAL 24 HOUR
  AND event_name IN ('signup_started', 'signup_completed')
GROUP BY hour
ORDER BY hour;
```

Active users is a simple `COUNT(DISTINCT session_id)` with a 5-minute window. Top features ranks by unique user count. Error rate divides error events by total events per minute. Each query returns in under 100ms even at millions of rows — ClickHouse's columnar storage makes these aggregations trivially fast.

### Step 4: Build the Dashboard Frontend

```text
Create a React dashboard with four chart panels matching the aggregation queries.
Use recharts for rendering. Each panel polls its API endpoint every 5 seconds.
Add a connection status indicator and a time-range selector (last 1h, 6h, 24h).
Style it with Tailwind — dark theme, grid layout, responsive for tablet and desktop.
```

The frontend is a React app with four chart panels arranged in a 2x2 grid:

- **Active Users** — a single large number with a sparkline showing the last hour
- **Signup Funnel** — a bar chart with started/completed bars and conversion rate overlay
- **Top Features** — a horizontal bar chart ranked by unique users
- **Error Rate** — a line chart with a red threshold line at 1%

Each panel polls its API endpoint every 5 seconds. A connection status indicator in the header shows green when all four endpoints are responding, yellow when any is slow, and red when any is unreachable. The time-range selector (1h, 6h, 24h) passes the range to each query.

The dark theme with Tailwind keeps it readable on big screens and projectors. Responsive grid collapses to a single column on tablets.

### Step 5: Containerize and Deploy

```text
Write a docker-compose.yml that runs ClickHouse, the ingestion service, and the
dashboard frontend. Pin ClickHouse to version 24.1. Add volume mounts for
ClickHouse data persistence. Include an init script that creates the events table
on first boot. Add a .env.example with all required environment variables.
```

The Docker Compose file bundles all three components:

```yaml
# docker-compose.yml
services:
  clickhouse:
    image: clickhouse/clickhouse-server:24.1
    ports: ["8123:8123"]
    volumes:
      - clickhouse-data:/var/lib/clickhouse
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql

  ingestion:
    build: ./src/ingest
    ports: ["3001:3001"]
    environment:
      CLICKHOUSE_URL: http://clickhouse:8123
    depends_on: [clickhouse]

  dashboard:
    build: ./src/dashboard
    ports: ["3000:3000"]
    depends_on: [ingestion]

volumes:
  clickhouse-data:
```

The init script (`init-db.sql`) creates the events table on first boot. The `.env.example` documents all required variables. One `docker compose up` and the full pipeline is running — ingestion, storage, and live dashboard.

## Real-World Example

A product manager at a fast-growing fintech startup needs to see real-time signup funnels during a marketing campaign launch. The existing analytics tool updates daily, which is useless during a 4-hour campaign window.

The event schema and ClickHouse table are ready in minutes. The ingestion service goes up with batching and validation, handling 5,000 events per second on a single node. Four aggregation queries power the dashboard: live users, funnel, feature ranking, error rate. The React frontend shows updating charts with 5-second refresh.

Docker Compose bundles everything — `docker compose up` and the dashboard is live. During the campaign, the team spots a 40% funnel drop-off at the email verification step in real time. They discover the verification email is landing in spam for Gmail users, fix the sender domain configuration, and watch the conversion rate recover within the hour. With daily analytics, they wouldn't have caught it until the campaign was already over.
