---
title: "Set Up A/B Testing Infrastructure for Product Experiments"
slug: set-up-ab-testing
description: "Build a complete experimentation platform with feature flags, user bucketing, event tracking, and statistical analysis."
skills: [ab-test-setup, analytics-tracking, feature-flag-manager]
category: development
tags: [ab-testing, experimentation, feature-flags, analytics, statistics]
---

# Set Up A/B Testing Infrastructure for Product Experiments

## The Problem

The product team wants to run experiments -- test a new checkout flow, try a different pricing layout, validate a recommendation algorithm. But without infrastructure, experiments are ad hoc: hardcoded `if-else` blocks, manual traffic splitting, and gut-feeling analysis. Results are unreliable because sample sizes are too small, metrics aren't tracked consistently, and there's no way to safely roll back a variant that's hurting conversion.

The last "experiment" involved a developer adding a feature flag that was actually a boolean in a config file, pushing it to production, and eyeballing the Stripe dashboard for a week. The conclusion: "revenue seemed about the same, so I guess it doesn't matter?" That's not an experiment. That's a guess. Building proper experimentation infrastructure has been on the roadmap for months, but it keeps getting deprioritized because it feels like a month-long project.

## The Solution

Use **feature-flag-manager** to implement the flag system and deterministic user bucketing, **ab-test-setup** to design statistically sound experiments, and **analytics-tracking** to wire up event collection and metric computation. The result: a full experimentation stack -- flag evaluation, consistent user assignment, event pipeline, and a results dashboard -- built in days instead of months.

## Step-by-Step Walkthrough

### Step 1: Build the Feature Flag System with Deterministic User Bucketing

The foundation of any A/B testing system: every user needs to be consistently assigned to the same variant, and the assignment needs to be independent across experiments.

```text
I need a feature flag system for A/B testing in my Next.js app with a Node.js API.
Requirements: deterministic user assignment (same user always sees same variant),
percentage-based rollout, and the ability to target by user attributes (plan type,
country, signup date). No third-party service -- I want to own the data.
```

Four files establish the core:

- **`experimentation/flags.ts`** -- Flag evaluation engine that resolves a flag name to a variant for a given user
- **`experimentation/bucketing.ts`** -- Deterministic hash-based assignment using MurmurHash3
- **`experimentation/targeting.ts`** -- Attribute-based targeting rules for filtering eligible users
- **`migrations/003_experiments.sql`** -- Tables for experiments, flags, and user assignments

The bucketing algorithm is the key to consistency:

```typescript
// MurmurHash3 produces a stable bucket 0-9999 per user per experiment
const bucket = murmurhash3(experimentId + userId) % 10000;

// 50/50 split: buckets 0-4999 -> control, 5000-9999 -> variant
// 90/10 rollout: buckets 0-8999 -> control, 9000-9999 -> variant
```

Same user, same experiment, same variant -- every time. Different experiments get independent assignments because the experiment ID is part of the hash input. A user in the "control" group for one experiment might be in the "variant" group for another, and that's exactly right. Experiments shouldn't leak into each other.

Targeting lets experiments run on subsets of users:

```json
{ "attribute": "plan", "operator": "in", "values": ["pro", "enterprise"] }
```

This experiment only runs for pro and enterprise users. Everyone else sees the default experience and isn't counted in the analysis.

### Step 2: Integrate Flag Evaluation into the Application

Flags need to work everywhere: server components, client components, and API routes. And they can't cause layout flicker -- nobody wants the checkout page to flash the old version before switching to the new one.

```text
Show me how to integrate this into my Next.js pages and API routes.
I need server-side evaluation (no flicker) and the flag values available
in both server components and client components.
```

Three integration files:

- **`experimentation/middleware.ts`** -- Evaluates all flags per request and injects results into response headers
- **`experimentation/context.ts`** -- React context that hydrates flag values from the server
- **`experimentation/hooks.ts`** -- `useFlag()` and `useExperiment()` hooks for client components

Server-side usage in API routes:

```typescript
const variant = getFlag('checkout-redesign', req);
if (variant === 'new-checkout') {
  return newCheckoutFlow(req);
}
```

Client-side usage in React components:

```typescript
const variant = useFlag('checkout-redesign');
return variant === 'new-checkout' ? <NewCheckout /> : <CurrentCheckout />;
```

Because flags evaluate on the server first and hydrate to the client, the user never sees a flash of the wrong variant. The server renders the correct version, and the client picks up where it left off.

### Step 3: Set Up Event Tracking for Experiment Metrics

An experiment without metrics is just a feature toggle. Every user action needs to be tagged with the experiments and variants that user is seeing.

```text
I need to track these events for experiments: page_view, button_click,
checkout_started, checkout_completed, and revenue. Each event should be
tagged with the active experiments and variants for that user.
```

The event schema ties every action to its experimental context:

```json
{
  "event": "checkout_completed",
  "userId": "user_abc",
  "properties": { "orderId": "ord_123", "revenue": 89.99 },
  "experiments": {
    "checkout-redesign": "new-checkout",
    "pricing-layout": "control"
  },
  "timestamp": "2026-02-17T14:30:00Z"
}
```

Every event automatically includes the user's active experiments and their assigned variants. No manual tagging required -- the tracking layer reads from the flag evaluation context.

Events go into PostgreSQL with JSONB columns for `properties` and `experiments`, partitioned by month for query performance. The client buffers events and flushes every 5 seconds or every 10 events, whichever comes first -- balancing data freshness against request overhead.

### Step 4: Build the Analysis Dashboard

This is where the experiment either proves its hypothesis or doesn't. The dashboard needs to show not just results, but whether those results are statistically meaningful.

```text
Build a results page that shows for each experiment: variant distribution,
conversion rate per variant, statistical significance (p-value and confidence
interval), and estimated sample size to reach significance.
```

The analysis engine (`experimentation/analysis.ts`) and dashboard (`app/admin/experiments/page.tsx`) display results like this:

**Variant distribution**: control = 4,812 users (50.3%), variant = 4,756 users (49.7%). Close enough to 50/50 -- the bucketing is working correctly.

**Conversion metric** (`checkout_completed` rate):
- Control: 3.2% (154 out of 4,812)
- Variant: 4.1% (195 out of 4,756)
- Relative lift: +28.1%

**Statistical significance**:
- Test: two-proportion z-test
- p-value: 0.0142
- 95% confidence interval for the difference: +0.2% to +1.6%
- Status: **SIGNIFICANT** (p < 0.05)

When an experiment hasn't reached significance yet, the dashboard shows how much longer to wait: current sample of 9,568 users, estimated 14,200 needed (at 80% power, alpha 0.05), approximately 6 days remaining at current traffic. This prevents the most common experimentation mistake -- calling a winner too early.

### Step 5: Roll Out the Winner and Clean Up

A winning variant still needs a careful rollout. Jumping from 50% to 100% overnight risks catching edge cases that didn't appear in the experiment.

```text
The checkout experiment is significant. Roll it out to 100% of users,
then clean up the experiment code. Show me the safe rollout process.
```

The rollout follows three phases:

**Gradual ramp** -- Day 1: increase the variant allocation from 50% to 75%. Day 2: if error rates and latency are stable, go to 100%. The bucketing system makes this trivial -- just change the split threshold.

**Monitor at 100%** for 48 hours, watching error rate, p95 latency, and revenue per session. An auto-rollback trigger fires if the error rate exceeds 2x baseline. This catches issues that only appear at full traffic -- the kind that a 50% test might miss.

**Code cleanup** -- Once 100% is stable, a cleanup script (`scripts/cleanup-experiment.ts`) finds all 7 files that reference `checkout-redesign`, and the team removes the branching logic. The `<CurrentCheckout />` component gets deleted. The experiment gets archived (data retained for 90 days) and removed from the active experiments config.

This is where most teams get sloppy -- old experiment code lingers for months, creating confusion about which version is "real." The cleanup script makes it mechanical instead of aspirational.

## Real-World Example

A product manager at a mid-size SaaS company wants to test whether moving the pricing toggle from a dropdown to radio buttons increases plan upgrades. The engineering team has zero experimentation infrastructure -- previous "tests" were config file booleans and gut feelings.

On Monday, a developer builds the flag system with deterministic bucketing. Flag evaluation integrates into their Next.js middleware -- zero flicker for users. On Tuesday, event tracking goes live, capturing page views on the pricing page and upgrade completions, each tagged with the experiment context.

Two weeks later, the dashboard tells the story: the radio button variant shows a 15% lift in upgrades with a p-value of 0.03. The confidence interval is tight enough to trust. They roll out the winner on Wednesday and start their next experiment the same week.

Experimenting becomes routine instead of a special project. Over the next quarter, the team runs 8 experiments -- 3 winners, 2 neutral results, and 3 that would have been shipped without data if they'd gone with gut instinct. Those 3 losers would have cost an estimated 4% conversion rate drop. The infrastructure paid for itself by preventing the first bad ship.
