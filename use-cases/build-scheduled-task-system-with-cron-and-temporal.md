---
title: Build a Scheduled Task System with Cron and Temporal
slug: build-scheduled-task-system-with-cron-and-temporal
description: >-
  Design a robust scheduled task system combining Unix cron for simple recurring
  jobs with Temporal for complex durable workflows — manage billing cycles,
  data aggregation, cleanup jobs, and report generation.
skills:
  - cron
  - temporal
  - docker-compose
  - redis
  - resend
category: infrastructure
tags:
  - scheduling
  - cron
  - workflows
  - background-jobs
  - automation
---

# Build a Scheduled Task System with Cron and Temporal

Aisha's SaaS runs dozens of scheduled tasks: daily billing reconciliation, weekly usage reports, hourly cache warming, monthly data archival. Some are simple one-liners, others are multi-step workflows that take 30 minutes and must handle failures gracefully. She's currently using a mix of `setTimeout`, node-cron, and "just restart if it fails" — and it's falling apart. She needs a proper scheduling system.

## Step 1: System Cron for Simple Recurring Jobs

```bash
# crontab -e — Simple jobs that run on the host
# Syntax: minute hour day month weekday command

# Every 5 minutes: health check
*/5 * * * * curl -sf https://app.example.com/api/health >> /var/log/healthcheck.log 2>&1

# Every hour: clear expired sessions
0 * * * * /app/scripts/clear-expired-sessions.sh >> /var/log/cron/sessions.log 2>&1

# Daily at 3 AM UTC: database vacuum
0 3 * * * /app/scripts/db-vacuum.sh >> /var/log/cron/vacuum.log 2>&1

# Weekly on Monday at 6 AM: generate usage reports
0 6 * * 1 /app/scripts/weekly-reports.sh >> /var/log/cron/reports.log 2>&1

# Monthly on the 1st at midnight: archive old data
0 0 1 * * /app/scripts/archive-data.sh >> /var/log/cron/archive.log 2>&1
```

```bash
#!/bin/bash
# scripts/clear-expired-sessions.sh — Simple but reliable
set -euo pipefail

LOCK_FILE="/tmp/clear-sessions.lock"

# Prevent overlapping runs
if [ -f "$LOCK_FILE" ]; then
  LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE") ))
  if [ $LOCK_AGE -lt 3600 ]; then
    echo "$(date -u +%FT%TZ) SKIP: Lock held for ${LOCK_AGE}s"
    exit 0
  fi
  echo "$(date -u +%FT%TZ) WARN: Stale lock (${LOCK_AGE}s), removing"
  rm "$LOCK_FILE"
fi

trap 'rm -f "$LOCK_FILE"' EXIT
touch "$LOCK_FILE"

DELETED=$(psql "$DATABASE_URL" -tAc "
  DELETE FROM sessions
  WHERE expires_at < NOW()
  RETURNING id
" | wc -l)

echo "$(date -u +%FT%TZ) Cleared $DELETED expired sessions"

# Alert if unusually high
if [ "$DELETED" -gt 10000 ]; then
  curl -s -X POST "$SLACK_WEBHOOK" \
    -d "{\"text\": \"⚠️ Cleared $DELETED expired sessions — unusual volume\"}"
fi
```

## Step 2: Temporal for Complex Workflows

```typescript
// src/workflows/billing-reconciliation.ts
import { proxyActivities, sleep, defineSignal, setHandler } from "@temporalio/workflow";
import type * as activities from "../activities/billing";

const { fetchInvoices, reconcilePayments, generateReport, sendReport, notifySlack } =
  proxyActivities<typeof activities>({
    startToCloseTimeout: "5 minutes",
    retry: { maximumAttempts: 3 },
  });

export const cancelSignal = defineSignal("cancel");

export async function billingReconciliation(date: string): Promise<void> {
  let cancelled = false;
  setHandler(cancelSignal, () => { cancelled = true; });

  // Step 1: Fetch all invoices for the period
  const invoices = await fetchInvoices(date);
  if (cancelled) return;

  // Step 2: Reconcile with payment provider
  const discrepancies = await reconcilePayments(invoices);

  // Step 3: Generate report
  const reportUrl = await generateReport({ date, invoices, discrepancies });

  // Step 4: Notify based on results
  if (discrepancies.length > 0) {
    await notifySlack({
      channel: "#billing-alerts",
      message: `⚠️ ${discrepancies.length} discrepancies found for ${date}`,
      reportUrl,
    });
  }

  await sendReport({ to: "finance@company.com", reportUrl, date });
}
```

## Step 3: Schedule Temporal Workflows

```typescript
// src/workers/scheduler.ts
import { Client } from "@temporalio/client";

const client = new Client();

// Create a schedule for billing reconciliation
await client.schedule.create({
  scheduleId: "daily-billing-reconciliation",
  spec: {
    calendars: [{ hour: 4, minute: 0 }], // 4 AM UTC daily
  },
  action: {
    type: "startWorkflow",
    workflowType: "billingReconciliation",
    args: [new Date().toISOString().split("T")[0]],
    taskQueue: "billing",
    workflowId: `billing-recon-${new Date().toISOString().split("T")[0]}`,
  },
  policies: {
    overlap: "SKIP", // Don't start if previous is still running
    catchupWindow: "1 hour", // Run missed schedules within 1 hour
  },
});
```

## Step 4: Cron Monitoring Script

```bash
#!/bin/bash
# scripts/cron-monitor.sh — Run as a cron job itself to check others
set -euo pipefail

ALERT_WEBHOOK="$SLACK_WEBHOOK"

check_job() {
  local name="$1"
  local log_file="$2"
  local max_age_hours="$3"

  if [ ! -f "$log_file" ]; then
    echo "ALERT: $name — log file missing"
    return 1
  fi

  local last_modified=$(stat -c %Y "$log_file")
  local now=$(date +%s)
  local age_hours=$(( (now - last_modified) / 3600 ))

  if [ $age_hours -gt $max_age_hours ]; then
    echo "ALERT: $name — last run ${age_hours}h ago (max: ${max_age_hours}h)"
    return 1
  fi

  # Check last line for errors
  local last_line=$(tail -1 "$log_file")
  if echo "$last_line" | grep -qi "error\|fail\|fatal"; then
    echo "ALERT: $name — last run had errors: $last_line"
    return 1
  fi

  echo "OK: $name — last run ${age_hours}h ago"
  return 0
}

FAILURES=""
check_job "session-cleanup" "/var/log/cron/sessions.log" 2 || FAILURES="$FAILURES\n• Session cleanup"
check_job "db-vacuum" "/var/log/cron/vacuum.log" 25 || FAILURES="$FAILURES\n• DB vacuum"
check_job "weekly-reports" "/var/log/cron/reports.log" 170 || FAILURES="$FAILURES\n• Weekly reports"

if [ -n "$FAILURES" ]; then
  curl -s -X POST "$ALERT_WEBHOOK" \
    -d "{\"text\": \"🚨 Cron job failures detected:$FAILURES\"}"
fi
```

## Summary

Aisha now has a two-tier scheduling system: Unix cron handles simple recurring jobs (session cleanup, health checks, db vacuum) with lock files to prevent overlap and monitoring to catch failures. Temporal handles complex multi-step workflows (billing reconciliation) with automatic retries, durability, and signals for cancellation. The cron monitor script watches all jobs and alerts Slack if anything goes wrong. Simple jobs stay simple, complex jobs get the reliability they need.
