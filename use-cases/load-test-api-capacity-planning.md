---
title: "Load Test APIs and Plan Capacity with AI"
slug: load-test-api-capacity-planning
description: "Design realistic load test scenarios, execute them with k6 or wrk, and translate results into infrastructure capacity plans."
skills: [api-load-tester, capacity-planner]
category: devops
tags: [load-testing, capacity-planning, performance, api, scalability]
---

# Load Test APIs and Plan Capacity with AI

## The Problem

Teams ship APIs without knowing their breaking point. A marketing campaign drives 5x normal traffic, and the checkout endpoint starts returning 503s. Post-mortems reveal nobody tested beyond 50 concurrent users, but production hit 800. Writing load tests is tedious -- you need realistic payloads, proper ramp-up patterns, authentication flows, and meaningful assertions. Then you need to translate "p99 latency hit 2.3s at 400 RPS" into "we need X more pods or Y database connections."

## The Solution

Using the **api-load-tester** skill to generate and execute realistic k6 load test scripts from API specs or route definitions, and **capacity-planner** to analyze the results and produce scaling recommendations with cost estimates, the agent turns vague anxiety about traffic into concrete infrastructure plans.

## Step-by-Step Walkthrough

### Step 1: Generate Load Test Scenarios from API Routes

```text
Look at our Express.js API in ./src/routes/ and generate k6 load test scripts.
Focus on the checkout flow: POST /api/cart/add, POST /api/orders/create, and
GET /api/orders/:id. Use realistic payloads based on our TypeScript interfaces
in ./src/types/. Include authentication with a JWT token flow.
```

The agent reads route definitions and TypeScript interfaces, then generates a k6 script with realistic payloads -- not placeholder data. Product IDs pull from the actual range, quantities follow realistic distributions, and size variants match what the interfaces define:

```javascript
// load-tests/checkout-flow.js (k6 script)
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const orderLatency = new Trend('order_creation_latency');

export const options = {
  scenarios: {
    ramp_up: {
      executor: 'ramping-vus',
      startVUs: 10,
      stages: [
        { duration: '2m', target: 50 },
        { duration: '5m', target: 200 },
        { duration: '3m', target: 500 },
        { duration: '2m', target: 500 },  // sustain peak
        { duration: '2m', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<800', 'p(99)<2000'],
    errors: ['rate<0.05'],
  },
};

export default function () {
  const cartPayload = JSON.stringify({
    productId: `prod_${Math.floor(Math.random() * 500) + 1}`,
    quantity: Math.floor(Math.random() * 3) + 1,
    variant: ['S', 'M', 'L', 'XL'][Math.floor(Math.random() * 4)],
  });

  const addToCart = http.post(`${__ENV.BASE_URL}/api/cart/add`, cartPayload, {
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${__ENV.TOKEN}` },
  });
  check(addToCart, { 'cart add 200': (r) => r.status === 200 });
  // ... order creation and verification steps
}
```

The ramp-up pattern is intentional: start at 10 VUs to establish a baseline, climb to 500 over 10 minutes to find the breaking point, sustain peak for 2 minutes to identify resource exhaustion, then cool down to observe recovery behavior.

### Step 2: Run the Load Test and Analyze Results

```text
Run the checkout flow load test against our staging environment at
https://staging-api.example.com. Ramp up to 500 virtual users over 14 minutes.
Show me the results with focus on p95/p99 latency and error rates at each stage.
```

The results tell a clear story -- performance degrades sharply above 350 concurrent users:

| Stage | VUs | RPS | p50 | p95 | p99 | Error Rate |
|-------|-----|-----|-----|-----|-----|------------|
| Ramp 0-50 | 50 | 120 | 45ms | 89ms | 142ms | 0.0% |
| Ramp 50-200 | 200 | 380 | 62ms | 210ms | 480ms | 0.2% |
| Ramp 200-500 | 500 | 620 | 185ms | 890ms | 2,340ms | 3.8% |
| Sustain 500 | 500 | 540 | 240ms | 1,200ms | 3,100ms | 7.2% |

**Breaking point: ~350 VUs / 520 RPS.** The p95 crosses the 800ms threshold at 320 VUs. Error rate crosses 5% at 420 VUs. The primary bottleneck is the database connection pool -- maxed at 20 connections, exhausted at 380 RPS. Notice that RPS actually drops from 620 to 540 during the sustain phase as the system buckles under contention.

The slowest endpoints under load:

- `POST /api/orders/create` -- p99 of 3,100ms at peak (DB write contention)
- `POST /api/cart/add` -- p99 of 890ms at peak (Redis connection queuing)
- `GET /api/orders/:id` -- p99 of 320ms at peak (acceptable)

### Step 3: Generate the Capacity Plan

```text
Based on these results, create a capacity plan. We expect 3x current traffic
for our product launch in 6 weeks. Current production runs 3 API pods and
a single RDS db.r5.large with max_connections=100. What do we need?
```

Current baseline: ~180 RPS sustained, 3 API pods, 1x db.r5.large. Target: 540 RPS sustained with p95 under 500ms and error rate under 1%.

| Change | What | Monthly Cost Delta |
|--------|------|--------------------|
| DB connection pool | `pool_size`: 20 -> 60, `max_connections`: 100 -> 200 | $0 (config change) |
| Scale API pods | 3 -> 8 pods, HPA min=5 max=12 target CPU 65% | +$175/mo |
| RDS upgrade | db.r5.large -> db.r5.xlarge (2x memory and network) | +$274/mo |
| Read replica | For `GET /api/orders/:id` reads | +$274/mo |
| Redis upgrade | r6g.large (current connection limit insufficient at 500+ VUs) | +$86/mo |

**Total additional cost: ~$809/month.** Cost per 1,000 RPS drops from $1,890/month (current) to $1,498/month -- better efficiency at scale. The biggest win is free: the connection pool config change alone would handle another 100 RPS.

### Step 4: Create the Pre-Launch Verification Test

```text
Generate a final verification test script I can run after applying these
changes to confirm we can handle 3x traffic with acceptable latency.
```

The verification script targets 600 VUs (20% headroom above the 540 RPS target) with stricter thresholds: p95 under 500ms and error rate under 1%. It runs the full checkout flow -- cart add, order create, order verify -- with realistic think time between steps to simulate actual user behavior rather than synthetic hammering.

The script also includes a soak phase: 500 VUs sustained for 30 minutes to catch memory leaks, connection pool exhaustion, and other problems that only appear under sustained load. A quick spike test is not enough -- some bottlenecks only manifest after the connection pool has been churning for 15 minutes or the garbage collector starts falling behind.

## Real-World Example

Tomas, backend lead at a 25-person e-commerce startup, has a product launch in 6 weeks with a TV ad campaign expected to drive 3x normal traffic. The team has never load-tested beyond manual curl commands.

He points the agent at the Express.js routes and asks for k6 scripts covering the full purchase flow. The agent generates scripts with realistic product payloads derived from the TypeScript interfaces, including JWT authentication and proper ramp-up patterns.

Running against staging reveals the breaking point at 350 concurrent users -- well below the 800 expected during the TV spot. The bottleneck is a database connection pool of 20, exhausting at 380 RPS. The capacity plan recommends increasing the pool to 60, upgrading the RDS instance one size, and scaling API pods from 3 to 8 with autoscaling.

After applying the changes, a verification test shows p95 at 310ms with 600 VUs and a 0.3% error rate -- well within targets.

The launch handles peak traffic of 720 concurrent users with zero downtime. p95 latency stays under 400ms throughout the TV spot. Total infrastructure cost increase: $809/month -- far less than the revenue at risk from a checkout page returning 503s during a TV commercial.

The load test scripts stay in the repository as part of the CI pipeline, running a lighter version (100 VUs for 5 minutes) on every deploy to staging. Three months later, a database query regression gets caught in staging because the load test flagged a p95 spike -- a problem invisible to manual testing but catastrophic at production scale.
