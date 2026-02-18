---
title: "Manage Feature Flags and Gradual Rollouts"
slug: manage-feature-flags-gradual-rollouts
description: "Implement a feature flag system with percentage-based rollouts, user targeting, and kill switches to ship features safely without risky big-bang deployments."
skills: [feature-flag-manager, ab-test-setup, analytics-tracking]
category: development
tags: [feature-flags, rollouts, canary, kill-switch, experimentation, deployment]
---

# Manage Feature Flags and Gradual Rollouts

## The Problem

Ravi is the engineering lead at a 25-person B2B SaaS company selling an invoicing platform. They ship weekly, and every release is a coin flip. Last month, a new PDF export engine went live to all 12,000 accounts simultaneously. It worked perfectly in staging. In production, it choked on invoices with more than 200 line items — something only 3% of customers had, but those customers were enterprise accounts paying $2,400/month each.

The rollback took 47 minutes. During that window, 340 invoices failed to generate. 14 enterprise customers opened urgent tickets. The VP of Sales spent the next two days on apology calls. Revenue at risk: $280,000 in annual contracts from frustrated accounts.

This wasn't the first time. Three months earlier, a redesigned dashboard confused users so badly that support tickets tripled for a week. The team had no way to show the new UI to a small group first, measure the impact, and expand gradually. It was all-or-nothing.

The deploy process: merge to main, CI builds, deploy to all servers, pray. No percentage rollouts. No user targeting. No kill switch that doesn't require a full redeploy. The team avoids shipping on Fridays, avoids shipping before holidays, and increasingly avoids shipping anything that touches core flows. Feature velocity has dropped 40% in six months because everyone is afraid of the blast radius.

Meanwhile, the product team wants to run experiments — test a new pricing page, try a different onboarding flow, show a chatbot to free-tier users only. Without feature flags, every experiment requires a branch, a deploy, and a way to segment users that doesn't exist.

## The Solution

Using the **feature-flag-manager**, **ab-test-setup**, and **analytics-tracking** skills, the system builds a self-hosted feature flag engine with percentage-based rollouts, user targeting rules, real-time kill switches, and analytics integration — so features ship to 1% first, then 10%, then 50%, then everyone, with data at every stage and an instant off-switch that doesn't require a deploy.

## Step-by-Step Walkthrough

### Step 1: Design the Flag Data Model and Evaluation Engine

The core of any feature flag system is deterministic evaluation — the same user must see the same variant across sessions, devices, and servers, without storing assignments. MurmurHash on `userId + flagName` gives a stable number between 0 and 100 that determines bucketing:

```typescript
// lib/flags/evaluator.ts
import murmurhash from "murmurhash";

interface FlagRule {
  type: "boolean" | "percentage" | "user_list" | "attribute";
  enabled: boolean;
  percentage?: number;
  userIds?: string[];
  accountIds?: string[];
  attribute?: { key: string; operator: "eq" | "in" | "gt" | "lt"; value: any };
}

interface FlagDefinition {
  name: string;
  rules: FlagRule[];     // Evaluated in order — first match wins
  defaultValue: boolean;
  killSwitch: boolean;   // When true, overrides everything → returns false
}

function evaluateFlag(flag: FlagDefinition, context: UserContext): boolean {
  // Kill switch is the nuclear option — overrides all rules
  if (flag.killSwitch) return false;

  for (const rule of flag.rules) {
    if (!rule.enabled) continue;

    switch (rule.type) {
      case "boolean":
        return rule.enabled;

      case "percentage":
        // Deterministic: same user + flag always produces same bucket
        const hash = murmurhash.v3(`${context.userId}:${flag.name}`);
        const bucket = hash % 100;
        return bucket < (rule.percentage ?? 0);

      case "user_list":
        if (rule.userIds?.includes(context.userId)) return true;
        if (rule.accountIds?.includes(context.accountId)) return true;
        continue;  // No match — try next rule

      case "attribute":
        if (matchesAttribute(rule.attribute, context)) return true;
        continue;
    }
  }
  return flag.defaultValue;
}
```

The `killSwitch` field is separate from the rules — it's a single boolean that trumps everything. When an incident happens, toggling it to `true` disables the flag in under 3 seconds via Redis pub/sub, no deploy needed. No more 47-minute rollbacks.

### Step 2: Build the Server-Side SDK with Local Caching

Flag checks happen in API handlers on every request. A network call per check would add unacceptable latency. Instead, rules are cached locally and kept in sync via Redis pub/sub — evaluation happens in-process in under 1ms:

```typescript
// lib/flags/client.ts
import Redis from "ioredis";

class FlagClient {
  private rules: Map<string, FlagDefinition> = new Map();
  private redis: Redis;

  async initialize() {
    // Load all flag definitions on startup
    const flags = await db.query("SELECT * FROM feature_flags WHERE archived = false");
    for (const flag of flags) {
      this.rules.set(flag.name, flag);
    }

    // Subscribe to real-time updates — no polling, no stale cache
    this.redis = new Redis(process.env.REDIS_URL);
    this.redis.subscribe("flag-updates");
    this.redis.on("message", (channel, message) => {
      const updated = JSON.parse(message);
      this.rules.set(updated.name, updated);
      console.log(`[flags] Updated ${updated.name}: ${JSON.stringify(updated.rules)}`);
    });
  }

  isEnabled(flagName: string, context: UserContext): boolean {
    const flag = this.rules.get(flagName);
    if (!flag) return false;  // Unknown flags default to off — safe
    return evaluateFlag(flag, context);
  }
}

// Singleton — initialized once at app startup
export const flags = new FlagClient();
```

Usage in an API handler looks like this:

```typescript
// routes/invoices.ts
router.post("/:id/export-pdf", async (req, res) => {
  const context = { userId: req.user.id, accountId: req.user.accountId, plan: req.user.plan };

  if (flags.isEnabled("new-pdf-engine", context)) {
    return newPdfEngine.export(req.params.id, res);
  }
  return legacyPdfEngine.export(req.params.id, res);
});
```

When the admin UI changes a flag, it writes to PostgreSQL and publishes to Redis. Every server picks up the change within 2 seconds. No redeploy, no restart, no CI pipeline.

### Step 3: Create the React Hook for Client-Side Flags

The frontend needs flags too — showing or hiding UI elements, rendering different components for A/B tests. A React hook bootstraps flag assignments on page load and updates in real time via Server-Sent Events:

```typescript
// hooks/useFeatureFlag.ts
import { createContext, useContext, useEffect, useState } from "react";

const FlagContext = createContext<Record<string, boolean>>({});

export function FlagProvider({ children }: { children: React.ReactNode }) {
  const [flags, setFlags] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetch("/api/flags/evaluate").then(r => r.json()).then(setFlags);

    // Real-time updates via SSE — kill switches take effect immediately
    const sse = new EventSource("/api/flags/stream");
    sse.onmessage = (event) => {
      const { name, value } = JSON.parse(event.data);
      setFlags(prev => ({ ...prev, [name]: value }));
    };
    return () => sse.close();
  }, []);

  return <FlagContext.Provider value={flags}>{children}</FlagContext.Provider>;
}

export function useFeatureFlag(name: string): boolean {
  return useContext(FlagContext)[name] ?? false;
}
```

Usage is straightforward — `useFeatureFlag("redesigned-dashboard")` returns a boolean, and the SSE connection means a kill switch toggled in the admin UI propagates to the browser within seconds. No page refresh required.

### Step 4: Configure the Five Initial Flags

With the engine in place, set up the five flags that address Ravi's immediate pain points. Each uses a different targeting strategy:

| Flag | Type | Targeting |
|------|------|-----------|
| `new-pdf-engine` | Percentage | 5% of accounts (600 of 12,000) |
| `redesigned-dashboard` | Percentage | 50/50 A/B test |
| `ai-chatbot` | Attribute | Free-tier accounts in US and UK (2,100) |
| `bulk-invoice-api` | User list | 3 specific enterprise account IDs |
| `maintenance-mode` | Boolean | Global kill switch, off by default |

```typescript
// scripts/seed-flags.ts — abbreviated
const initialFlags: FlagDefinition[] = [
  { name: "new-pdf-engine",
    rules: [{ type: "percentage", enabled: true, percentage: 5 }],
    defaultValue: false, killSwitch: false },
  { name: "redesigned-dashboard",
    rules: [{ type: "percentage", enabled: true, percentage: 50 }],
    defaultValue: false, killSwitch: false },
  { name: "ai-chatbot",
    rules: [
      { type: "attribute", enabled: true, attribute: { key: "plan", operator: "eq", value: "free" } },
      { type: "attribute", enabled: true, attribute: { key: "country", operator: "in", value: ["US", "UK"] } },
    ],
    defaultValue: false, killSwitch: false },
  { name: "bulk-invoice-api",
    rules: [{ type: "user_list", enabled: true, accountIds: ["acct_3kF8j", "acct_9mN2p", "acct_7xQ4r"] }],
    defaultValue: false, killSwitch: false },
  { name: "maintenance-mode",
    rules: [{ type: "boolean", enabled: false }],
    defaultValue: false, killSwitch: false },
];
```

The PDF engine at 5% means if the 200+ line item bug still exists, it affects 600 accounts instead of 12,000 — and the kill switch can stop it in 3 seconds instead of 47 minutes.

### Step 5: Wire Analytics and Build Rollout Automation

Flags without data are just guesses. Every flag evaluation gets sent to Mixpanel as a user property, so conversion rates and error rates can be compared between flag-on and flag-off groups:

```typescript
// lib/flags/analytics.ts
import mixpanel from "mixpanel";

function trackFlagAssignment(flagName: string, value: boolean, context: UserContext) {
  mixpanel.people.set(context.userId, {
    [`flag_${flagName}`]: value ? "treatment" : "control",
  });
  mixpanel.track("flag_evaluated", {
    distinct_id: context.userId,
    flag: flagName,
    variant: value ? "treatment" : "control",
    account_id: context.accountId,
    plan: context.plan,
  });
}
```

The rollout automation monitors these metrics and auto-progresses or auto-rolls-back:

```typescript
// jobs/rollout-monitor.ts — runs every hour via cron
async function checkRolloutHealth(flagName: string) {
  const flag = await db.featureFlags.findOne({ name: flagName });
  const metrics = await getMetricsForFlag(flagName);

  const treatmentErrorRate = metrics.treatment.errorRate;
  const controlErrorRate = metrics.control.errorRate;
  const p95Treatment = metrics.treatment.p95Latency;
  const p95Control = metrics.control.p95Latency;

  // Auto-rollback: error rate 2x higher than control group
  if (treatmentErrorRate > controlErrorRate * 2) {
    await updateFlagPercentage(flagName, 0);
    await notify(`ROLLBACK: ${flagName} — error rate ${treatmentErrorRate}% vs control ${controlErrorRate}%`);
    return;
  }

  // Auto-progress: metrics within threshold for 24h
  if (metrics.hoursAtCurrentPercentage >= 24 && treatmentErrorRate <= controlErrorRate * 1.1) {
    const nextStep = { 5: 25, 25: 50, 50: 100 };
    const current = flag.rules[0].percentage;
    const next = nextStep[current];
    if (next) {
      await updateFlagPercentage(flagName, next);
      await notify(`PROGRESS: ${flagName} — ${current}% → ${next}%`);
    }
  }
}
```

The progression ladder — 5% to 25% to 50% to 100% — takes a minimum of 72 hours to reach full rollout. Each step requires 24 hours of clean metrics. If error rate doubles at any step, the flag drops to 0% immediately and a Slack alert fires.

To prevent flags from becoming permanent tech debt, a daily hygiene job scans for flags at 100% for more than 14 days and sends reminders with the exact code references that need cleanup:

```typescript
// jobs/flag-hygiene.ts — daily at 9am
async function checkStaleFlags() {
  const staleFlags = await db.featureFlags.find({
    "rules.percentage": 100,
    updatedAt: { $lt: daysAgo(14) },
    archived: false,
  });
  for (const flag of staleFlags) {
    const refs = await searchCodebase(`flags.isEnabled\\(["']${flag.name}`);
    await notify(`FLAG HYGIENE: \`${flag.name}\` at 100% for ${daysSince(flag.updatedAt)} days. ${refs.length} code references to remove.`);
  }
}
```

## Real-World Example

Six weeks after rolling out the flag system, Ravi ships the PDF engine again — this time to 5% of accounts. On day two, the monitoring catches it: accounts with 200+ line items are hitting a memory limit, and the error rate in the treatment group is 4x higher than control. The automation drops the flag to 0% and fires a Slack alert. Total blast radius: 600 accounts. Total customer-facing impact: 23 failed PDFs, caught and retried automatically. Zero escalations to the VP of Sales.

The fix takes two days. The flag goes back to 5%, clean for 24 hours, auto-progresses to 25%, then 50%, then 100% over the next week. The entire rollout happens without a single support ticket.

The dashboard redesign runs as a 50/50 A/B test for three weeks. Mixpanel data shows the new design increases invoice creation by 12% but decreases PDF exports by 8%. The product team uses this data to iterate on the export flow before shipping to everyone — a decision that would have been impossible with the old deploy-and-pray approach.

Feature velocity rebounds. Teams ship 3x more frequently because small rollouts with instant rollback remove the fear. Kill switch response time went from 47 minutes (full redeploy) to under 3 seconds (toggle in admin UI). In the three months after adoption, zero full-blast-radius incidents — compared to two in the three months before. The Friday deploy freeze is officially over.
