---
title: Build a Data Pipeline with dbt and PostgreSQL
slug: build-data-pipeline-with-dbt-and-postgres
description: >-
  Transform raw data into analytics-ready models using dbt — build staging
  layers, business logic models, data tests, documentation, and automated
  freshness checks for a production data warehouse.
skills:
  - dbt
  - docker-compose
  - github-actions
category: data
tags:
  - dbt
  - data-engineering
  - analytics
  - sql
  - data-pipeline
---

# Build a Data Pipeline with dbt and PostgreSQL

Yara's analytics team writes SQL queries directly against production tables. Every analyst has their own version of "monthly active users" that gives different numbers. Queries are undocumented, untested, and break when the schema changes. dbt (data build tool) brings software engineering practices to SQL: version-controlled models, automated tests, documentation, and a DAG that ensures models build in the right order.

## Step 1: Initialize dbt Project

```bash
pip install dbt-postgres
dbt init analytics
cd analytics
```

```yaml
# profiles.yml
analytics:
  target: dev
  outputs:
    dev:
      type: postgres
      host: localhost
      user: analytics
      password: "{{ env_var('DB_PASSWORD') }}"
      port: 5432
      dbname: warehouse
      schema: analytics_dev
      threads: 4
    prod:
      type: postgres
      host: "{{ env_var('DB_HOST') }}"
      user: analytics
      password: "{{ env_var('DB_PASSWORD') }}"
      port: 5432
      dbname: warehouse
      schema: analytics
      threads: 8
```

## Step 2: Staging Models (Clean Raw Data)

```sql
-- models/staging/stg_users.sql
-- Staging: clean and standardize raw user data

WITH source AS (
    SELECT * FROM {{ source('app', 'users') }}
)

SELECT
    id AS user_id,
    LOWER(TRIM(email)) AS email,
    COALESCE(name, 'Unknown') AS name,
    CASE
        WHEN plan IS NULL THEN 'free'
        WHEN plan = '' THEN 'free'
        ELSE LOWER(plan)
    END AS plan,
    created_at,
    updated_at,
    deleted_at IS NOT NULL AS is_deleted
FROM source
WHERE created_at IS NOT NULL
```

```sql
-- models/staging/stg_events.sql
WITH source AS (
    SELECT * FROM {{ source('app', 'events') }}
)

SELECT
    id AS event_id,
    user_id,
    event_name,
    properties::jsonb AS properties,
    created_at AS event_at,
    DATE_TRUNC('day', created_at) AS event_date
FROM source
WHERE user_id IS NOT NULL
  AND created_at >= '2024-01-01'  -- Only process recent data
```

```yaml
# models/staging/sources.yml
version: 2

sources:
  - name: app
    database: production_db
    schema: public
    tables:
      - name: users
        freshness:
          warn_after: { count: 24, period: hour }
          error_after: { count: 48, period: hour }
        loaded_at_field: updated_at
      - name: events
        freshness:
          warn_after: { count: 1, period: hour }
          error_after: { count: 6, period: hour }
        loaded_at_field: created_at
      - name: subscriptions
      - name: invoices
```

## Step 3: Business Logic Models

```sql
-- models/marts/dim_users.sql
-- Dimension: user profile with computed attributes

{{ config(materialized='table') }}

WITH users AS (
    SELECT * FROM {{ ref('stg_users') }}
    WHERE NOT is_deleted
),

first_events AS (
    SELECT
        user_id,
        MIN(event_at) AS first_active_at,
        MAX(event_at) AS last_active_at,
        COUNT(DISTINCT event_date) AS active_days
    FROM {{ ref('stg_events') }}
    GROUP BY user_id
),

subscriptions AS (
    SELECT
        user_id,
        plan,
        status,
        started_at,
        ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY started_at DESC) AS rn
    FROM {{ ref('stg_subscriptions') }}
)

SELECT
    u.user_id,
    u.email,
    u.name,
    u.plan,
    u.created_at AS signed_up_at,
    fe.first_active_at,
    fe.last_active_at,
    fe.active_days,
    CASE
        WHEN fe.last_active_at >= CURRENT_DATE - INTERVAL '7 days' THEN 'active'
        WHEN fe.last_active_at >= CURRENT_DATE - INTERVAL '30 days' THEN 'at_risk'
        ELSE 'churned'
    END AS activity_status,
    DATE_PART('day', COALESCE(fe.first_active_at, u.created_at) - u.created_at) AS days_to_first_action,
    s.plan AS current_subscription_plan,
    s.status AS subscription_status
FROM users u
LEFT JOIN first_events fe ON fe.user_id = u.user_id
LEFT JOIN subscriptions s ON s.user_id = u.user_id AND s.rn = 1
```

```sql
-- models/marts/fct_daily_metrics.sql
-- Fact: daily aggregated metrics

{{ config(materialized='incremental', unique_key='metric_date') }}

WITH daily_signups AS (
    SELECT
        DATE_TRUNC('day', signed_up_at) AS metric_date,
        COUNT(*) AS new_users,
        COUNT(*) FILTER (WHERE plan != 'free') AS new_paid_users
    FROM {{ ref('dim_users') }}
    {% if is_incremental() %}
    WHERE signed_up_at >= (SELECT MAX(metric_date) FROM {{ this }})
    {% endif %}
    GROUP BY 1
),

daily_active AS (
    SELECT
        event_date AS metric_date,
        COUNT(DISTINCT user_id) AS daily_active_users,
        COUNT(*) AS total_events
    FROM {{ ref('stg_events') }}
    {% if is_incremental() %}
    WHERE event_date >= (SELECT MAX(metric_date) FROM {{ this }})
    {% endif %}
    GROUP BY 1
)

SELECT
    COALESCE(s.metric_date, a.metric_date) AS metric_date,
    COALESCE(s.new_users, 0) AS new_users,
    COALESCE(s.new_paid_users, 0) AS new_paid_users,
    COALESCE(a.daily_active_users, 0) AS dau,
    COALESCE(a.total_events, 0) AS total_events
FROM daily_signups s
FULL OUTER JOIN daily_active a ON s.metric_date = a.metric_date
```

## Step 4: Data Tests and Documentation

```yaml
# models/marts/schema.yml
version: 2

models:
  - name: dim_users
    description: "User dimension table with activity status and subscription info"
    columns:
      - name: user_id
        description: "Unique user identifier"
        tests:
          - unique
          - not_null
      - name: email
        tests:
          - unique
          - not_null
      - name: activity_status
        tests:
          - accepted_values:
              values: ['active', 'at_risk', 'churned']
      - name: plan
        tests:
          - not_null
          - accepted_values:
              values: ['free', 'pro', 'enterprise']

  - name: fct_daily_metrics
    description: "Daily aggregated business metrics"
    columns:
      - name: metric_date
        tests:
          - unique
          - not_null
      - name: dau
        tests:
          - not_null
```

```sql
-- tests/assert_dau_not_higher_than_total_users.sql
-- Custom test: DAU should never exceed total users
SELECT metric_date, dau
FROM {{ ref('fct_daily_metrics') }}
WHERE dau > (SELECT COUNT(*) FROM {{ ref('dim_users') }})
```

## Step 5: Run and Deploy

```bash
# Development
dbt run                    # Build all models
dbt test                   # Run all tests
dbt source freshness       # Check data freshness
dbt docs generate && dbt docs serve  # Browse documentation

# Production CI
dbt run --target prod --select tag:daily
dbt test --target prod
```

```yaml
# .github/workflows/dbt.yml
name: dbt
on:
  schedule:
    - cron: "0 6 * * *"  # Daily at 6 AM UTC
  push:
    branches: [main]

jobs:
  dbt-run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install dbt-postgres
      - run: dbt deps
      - run: dbt run --target prod
        env:
          DB_HOST: ${{ secrets.DB_HOST }}
          DB_PASSWORD: ${{ secrets.DB_PASSWORD }}
      - run: dbt test --target prod
      - run: dbt source freshness --target prod
```

## Summary

Yara's team now has a single source of truth for every metric. "Monthly active users" is defined once in `dim_users.sql`, version-controlled, tested, and documented. The staging layer cleans raw data (trimming emails, handling nulls), the marts layer implements business logic, and incremental models only process new data — the daily metrics build takes 30 seconds instead of 15 minutes. Data tests catch issues before dashboards show wrong numbers. `dbt docs` generates a browsable data catalog where analysts can see every model's SQL, dependencies, and column descriptions. When the production schema changes, `dbt test` catches the breakage in CI, not in a CEO dashboard.
