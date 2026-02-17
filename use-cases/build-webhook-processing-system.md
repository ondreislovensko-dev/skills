---
title: "Build a Webhook Processing System with Retry Logic"
slug: build-webhook-processing-system
description: "Set up a reliable webhook ingestion pipeline with signature verification, exponential backoff retries, and dead letter queues."
skills: [webhook-processor, batch-processor]
category: development
tags: [webhooks, retry-logic, event-driven, queues, backend]
---

# Build a Webhook Processing System with Retry Logic

## The Problem

Your application integrates with payment providers, version control platforms, and third-party APIs that push events via webhooks. Without proper handling, you lose events during deployments, process duplicates when providers retry, and have no visibility into failures. A missed payment webhook means a customer paid but never got access. A duplicate order webhook means charging someone twice. Most teams start with a naive `app.post('/webhook')` handler that processes inline — and it works until it doesn't. At scale, a 30-second downstream timeout causes the webhook sender to retry, your handler runs again, and now you have duplicate side effects with no easy way to debug what happened.

## The Solution

Use the **webhook-processor** skill to scaffold a production-grade ingestion pipeline and **batch-processor** to handle high-volume webhook bursts efficiently. The architecture: accept and acknowledge immediately, queue for async processing, verify signatures, deduplicate with idempotency keys, and retry failures with exponential backoff.

```bash
npx terminal-skills install webhook-processor
npx terminal-skills install batch-processor
```

## Step-by-Step Walkthrough

### 1. Scaffold the webhook receiver

```
Create a webhook ingestion endpoint for my Node.js/Express app. I need to handle
webhooks from a payment provider and a shipping tracking service. Each webhook
should be acknowledged with 200 immediately, then queued in Redis via BullMQ
for async processing. Include HMAC-SHA256 signature verification.
```

The agent creates `src/webhooks/receiver.ts` with route-per-source pattern, raw body parsing for signature verification, and BullMQ queue integration. It also generates `src/config/webhook-secrets.ts` reading signing secrets from environment variables.

### 2. Add retry logic and dead letter handling

```
Configure the webhook worker with exponential backoff: 5 retries starting at 3 seconds.
After all retries fail, move the job to a dead letter queue. Store dead letters in
a PostgreSQL table so we can inspect and replay them from an admin panel.
```

The agent creates `src/workers/webhook-worker.ts` with BullMQ retry configuration (3s → 9s → 27s → 81s → 243s), a `dead_letters` migration file, and `src/services/dead-letter-store.ts` that persists failed events with full payload, error message, and attempt count.

### 3. Implement idempotency to prevent duplicate processing

```
Add idempotency checking to the webhook pipeline. Use the provider's event ID
header when available, otherwise hash the payload. Store processed event IDs in
Redis with a 48-hour TTL. Skip any event that was already processed.
```

The agent adds `src/middleware/idempotency.ts` that extracts the idempotency key from `x-event-id`, `x-request-id`, or falls back to SHA-256 of the raw body. It checks Redis before enqueuing and sets BullMQ's `jobId` to the idempotency key so even concurrent deliveries are deduplicated at the queue level.

### 4. Add monitoring and alerting

```
Set up structured logging for webhook processing and add health metrics. I want to
track: events received per source, processing latency, retry rate, and dead letter
queue depth. Use prom-client for Prometheus-compatible metrics.
```

The agent creates `src/monitoring/webhook-metrics.ts` with four gauges/histograms, instruments the worker and receiver, and adds a `/metrics` endpoint. It also creates a sample alert rule: fire when dead letter queue depth exceeds 10 events in 5 minutes.

## Real-World Example

Marcus, a backend engineer at a mid-size e-commerce company, notices that 2-3 times per month, customers report paying for orders that never get confirmed. The root cause: the payment webhook handler occasionally times out when the inventory service is slow, causing the payment provider to retry. The original request eventually succeeds, then the retry also succeeds — resulting in a confirmed order but a stuck webhook that throws a duplicate key error and gets silently swallowed.

1. Marcus asks the agent to scaffold a webhook processing system with the queue-first architecture
2. The agent generates the receiver, worker, and idempotency middleware — replacing the inline handler with a 12ms acknowledge-and-queue pattern
3. Marcus asks the agent to add a dead letter queue with a Postgres backing store and a replay endpoint
4. The agent creates the migration, the store service, and a `POST /admin/webhooks/replay/:id` endpoint
5. After deploying, webhook processing failures drop to zero missed events — the three that fail due to a downstream outage land in the dead letter queue and Marcus replays them the next morning

Total setup time: 45 minutes instead of the 2-week estimate from the previous sprint planning.

## Related Skills

- [batch-processor](../skills/batch-processor/) — Process high-volume webhook bursts in configurable batch sizes
- [docker-helper](../skills/docker-helper/) — Containerize the webhook service with Redis for local development
- [cicd-pipeline](../skills/cicd-pipeline/) — Deploy the webhook service with zero-downtime rolling updates
