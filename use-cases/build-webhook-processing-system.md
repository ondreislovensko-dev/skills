---
title: "Build a Webhook Processing System with Error Monitoring"
slug: build-webhook-processing-system
description: "Create a resilient webhook processing system that handles high-volume incoming webhooks, processes them reliably, and monitors for failures with automatic retry and alerting."
skills: [webhook-processor, batch-processor, error-monitoring]
category: development
tags: [webhooks, event-processing, reliability, monitoring, async, api-integration]
---

# Build a Webhook Processing System with Error Monitoring

## The Problem

Lisa is the lead engineer at a 50-person fintech startup, and every high-traffic event turns into a crisis. Their system processes payment notifications, transaction updates, and dispute alerts from Stripe, but the webhook handler does everything synchronously in the HTTP request handler — 4-7 database queries, external API calls, and email notifications per webhook, taking 8-12 seconds for complex events like disputes.

Last month's flash sale disaster: 47,000 payment webhooks arrived in 3 hours. The server crashed after processing 12,000 events, losing 35,000 critical payment confirmations. Customers never received order confirmations, inventory was not updated, and the accounting team could not reconcile daily revenue. Recovery took 3 days of manual work.

The scariest part is the failures they don't know about. When a webhook fails, it is gone forever. No retry, no error tracking, no alerting. The team discovers missing payments during monthly reconciliation — sometimes 6 weeks later. Last quarter, they manually recovered $47,000 in lost transactions that were never processed. The payment processor does not guarantee delivery, so a dropped webhook means lost revenue unless someone catches it.

## The Solution

Using the **webhook-processor**, **batch-processor**, and **error-monitoring** skills, the agent builds a system that ingests webhooks in under 50ms, processes them asynchronously through specialized workers, batches high-volume events for efficiency, and monitors everything with intelligent alerting and automatic recovery.

The core architectural shift is simple: decouple ingestion from processing. Accept the webhook instantly, queue it reliably, and handle the heavy work in the background. This single change eliminates the cascading failure mode that brought the old system down.

## Step-by-Step Walkthrough

### Step 1: Set Up Reliable Webhook Ingestion

```text
Create a webhook processing system for Stripe events. I need to handle
5 types: payment_intent.succeeded, payment_intent.failed,
charge.dispute.created, invoice.payment_succeeded, and
customer.subscription.updated. Each webhook should be acknowledged
immediately (200 OK) then processed asynchronously. Include signature
verification, deduplication, and high-availability considerations.
```

The golden rule of webhook ingestion: respond fast, process later. The old system spent 8-12 seconds per webhook doing database queries, API calls, and email sends — all while Stripe waited for a response. When the response took too long, Stripe timed out and retried, creating duplicate processing and more load. A vicious cycle.

The new endpoint does exactly three things in under 50ms: verify the Stripe signature (reject spoofed webhooks immediately), check Redis for duplicate event IDs (24-hour TTL prevents reprocessing), and push to a BullMQ queue. Then it returns `200 OK`. All the heavy lifting happens in background workers.

Each event type routes to a specialized job with its own priority level:

| Event Type | Job | Priority |
|---|---|---|
| `payment_intent.succeeded` | PaymentConfirmationJob | High |
| `payment_intent.failed` | PaymentFailureJob | High |
| `charge.dispute.created` | DisputeHandlingJob | Urgent |
| `invoice.payment_succeeded` | InvoiceProcessingJob | Normal |
| `customer.subscription.updated` | SubscriptionSyncJob | Low |

The ingestion layer also handles the basics that the old system was missing: rate limiting at 1,000 requests/minute per IP (prevents abuse), request size capped at 1MB (prevents memory exhaustion from malformed payloads), webhook secret rotation support (so rotating the Stripe webhook secret does not cause downtime), and a health check endpoint for load balancer monitoring.

Horizontal scaling is built in from the start. The endpoint is stateless — all state lives in Redis and the database — so adding more instances behind a load balancer is a configuration change, not a code change.

### Step 2: Implement Async Processing with Batch Capabilities

```text
Create background workers to process the queued webhook events. Payment
events need individual processing with user balance updates and email
notifications. For high-volume events like subscription updates, process
them in batches of 50 to improve efficiency. Include proper error handling,
progress tracking, and retry logic.
```

Each event type gets a specialized worker tuned for its workload:

**PaymentConfirmationWorker** runs 10 jobs simultaneously. Each job updates the user balance, sends a confirmation email, and pushes to analytics. Average processing: 1.2 seconds per payment. Retry policy: 3 attempts with exponential backoff (2s, 8s, 32s). Failed balance updates trigger an immediate Slack alert because money is involved.

**DisputeHandlingWorker** processes disputes as urgent priority — they jump the queue because disputes have regulatory deadlines. Missing a dispute response window can cost thousands in automatic chargebacks. Each dispute creates a record, notifies the finance team, and freezes related transactions. Timeout is set to 30 seconds, with only 2 retry attempts because persistent dispute failures need human eyes immediately.

**SubscriptionSyncWorker** batches 50 subscription updates into a single database transaction. What would be 50 individual API calls becomes one batch write — processing 1,500 subscriptions per minute instead of 30. Subscription updates are low-priority by design: they are important but not time-sensitive. Batching them frees worker capacity for the payment events that customers are waiting on.

Total system capacity: **2,400+ webhook events per minute** sustained, up from the old system's 200/hour ceiling. That is a 720x improvement — enough to handle Black Friday traffic without breaking a sweat.

Per-worker throughput tracking monitors jobs per minute, average processing time by event type, retry rates, and memory usage. If a worker starts falling behind, the dashboard shows it before the queue backs up.

### Step 3: Add Comprehensive Error Monitoring and Alerting

```text
Set up error monitoring for the webhook system. Track processing failures,
identify patterns in failed webhooks, monitor system health metrics, and
create intelligent alerting that escalates based on error severity.
Include automated recovery for transient failures and detailed error
reporting.
```

Every failure gets classified into one of five categories: transient (network timeouts, temporary database issues), data errors (malformed payloads), business logic errors (user not found), system errors (memory exhaustion, worker crashes), and integration errors (email service down). The classification drives the response — transient errors get automatic retry, data errors get logged for investigation, system errors page the on-call engineer.

**Alert escalation tiers:**

- **Critical** (pages on-call): payment failure rate above 2% for 5+ minutes, dispute webhooks failing, all workers down, queue backlog over 5,000 jobs
- **Warning** (Slack notification): individual worker failure rate above 5%, processing time 3x above baseline, Redis memory above 80%
- **Daily digest** (automated Slack summary): total processed, success rate, average processing time, failed events breakdown, system uptime

The daily digest replaces the old approach of discovering problems during monthly reconciliation — six weeks of silence followed by a panicked Slack thread. A typical daily summary:

- **Total processed:** 23,847 webhooks (avg 994/hour)
- **Success rate:** 99.7% (target: 99.9%)
- **Average processing time:** 1.1 seconds (target: 1.5s)
- **Failed events:** 71 (auto-retried: 68, manual review: 3)
- **Queue backlog:** 23 jobs (healthy threshold: <100)
- **System uptime:** 99.95%

The error analysis dashboard goes deeper: a failed webhook inspector shows the full payload, error details, and retry history. Error trend analysis identifies systemic issues over time — if the email service starts degrading, the dashboard surfaces it before it becomes a crisis.

### Step 4: Implement Recovery and Admin Tools

```text
Build automated recovery mechanisms for common failure scenarios and admin
tools for manual intervention when needed. Include webhook replay
capabilities, failed job analysis, and emergency processing controls.
```

The self-healing layer handles the failures that used to require manual intervention:

- **Database reconnection** with exponential backoff — a brief Postgres restart no longer drops webhooks
- **Redis failover** to a backup instance — queue continuity even during cache failures
- **Worker auto-restart** with a cap of 3 restarts per hour — prevents infinite crash loops
- **Circuit breaker** on external integrations — if the email service is down, payments still process and emails queue for later. The circuit breaker opens after 5 consecutive failures, waits 60 seconds, then tries one request. If it succeeds, the circuit closes and normal traffic resumes
- **Queue rebalancing** — if one worker type falls behind, jobs redistribute to healthier workers automatically

The dead letter queue catches permanently failed webhooks. Instead of disappearing into the void, they sit in a persistent queue with their full payload, error details, and retry history. The admin dashboard at `/admin/webhooks` provides:

- **Search and replay:** find webhooks by date, type, status, or customer ID and replay them individually or in bulk
- **Emergency controls:** pause all processing during incidents, adjust worker concurrency, switch to backup systems
- **Diagnostics:** live webhook stream, processing timeline breakdown, error correlation across similar failures
- **Webhook simulator:** test processing with sample payloads before deploying changes

Recovery success rate: 94% of failures resolve automatically through retries. Only 0.3% of webhooks need manual intervention. Mean time to recovery: 2.3 minutes from failure to successful retry.

The contrast with the old system is stark: before, 100% of failures required manual intervention (once someone noticed them, weeks later). Now, 94% resolve themselves, 6% need a quick admin action, and zero disappear silently.

## Real-World Example

Lisa's team deploys the new system on a Monday and runs it in shadow mode alongside the old handler for a week. Both systems process the same webhooks, but only the old system's results are written to the production database. The monitoring dashboard shows the new system processing 100% of events that the old system handles, plus catching 3% of events that the old system had been silently dropping — events that previously disappeared and showed up as reconciliation discrepancies weeks later.

The real test comes during the next product launch: 15,000 orders in 2 hours. The old system would have crashed after 4,000 payments. The new system ingests every webhook in under 25ms, processes them through the worker pool, and finishes the entire backlog within 30 minutes of the traffic spike ending. Zero lost webhooks. Every customer gets an instant payment confirmation.

After 60 days in production: the webhook processing success rate is 99.97%, $15,000/month in previously lost payments is recovered, and the support team spends 15 minutes per week on webhook issues instead of 8 hours. The system handles 180,000+ webhooks monthly without manual intervention. Customer satisfaction scores climb from 7.2 to 9.1 because order confirmations now arrive instantly instead of not at all.
