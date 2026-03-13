---
title: Set Up Sentry Error Tracking for a Full-Stack App
slug: set-up-sentry-error-tracking-for-fullstack-app
description: >-
  Integrate Sentry across frontend and backend for real-time error tracking,
  performance monitoring, session replay, and release tracking — catch bugs
  before users report them.
skills:
  - sentry
  - github-actions
category: observability
tags:
  - error-tracking
  - sentry
  - monitoring
  - debugging
  - performance
---

# Set Up Sentry Error Tracking for a Full-Stack App

Oleg's team finds out about bugs from customer support tickets — days after they start happening. They have no idea which deploy introduced a regression, how many users are affected, or what the user was doing when it crashed. Sentry gives them instant error alerts with full stack traces, breadcrumbs of what happened before the error, session replays showing the user's screen, and performance monitoring to catch slow transactions.

## Step 1: Next.js Frontend Setup

```bash
npx @sentry/wizard@latest -i nextjs
```

```typescript
// sentry.client.config.ts
import * as Sentry from "@sentry/nextjs";

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: process.env.NODE_ENV === "production" ? 0.2 : 1.0,
  replaysSessionSampleRate: 0.1,
  replaysOnErrorSampleRate: 1.0,

  integrations: [
    Sentry.replayIntegration({
      maskAllText: false,
      maskAllInputs: true,   // Mask form inputs for privacy
      blockAllMedia: false,
    }),
    Sentry.browserTracingIntegration(),
    Sentry.feedbackIntegration({
      colorScheme: "system",
      showBranding: false,
    }),
  ],

  beforeSend(event) {
    // Don't send errors from browser extensions
    if (event.exception?.values?.[0]?.stacktrace?.frames?.some(
      (f) => f.filename?.includes("extension://")
    )) {
      return null;
    }
    return event;
  },
});
```

## Step 2: Backend API Setup

```typescript
// src/instrument.ts — Import before everything else
import * as Sentry from "@sentry/node";

Sentry.init({
  dsn: process.env.SENTRY_DSN,
  environment: process.env.NODE_ENV,
  tracesSampleRate: 0.5,
  profilesSampleRate: 0.1,
  integrations: [
    Sentry.httpIntegration(),
    Sentry.expressIntegration(),
    Sentry.prismaIntegration(),
  ],
});
```

```typescript
// src/server.ts
import "./instrument"; // Must be first import
import express from "express";
import * as Sentry from "@sentry/node";

const app = express();

// Routes go here...

// Sentry error handler must be after all routes
Sentry.setupExpressErrorHandler(app);

// Custom error handler after Sentry's
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  res.status(500).json({
    error: "Internal server error",
    sentryId: (res as any).sentry, // Include for support reference
  });
});
```

## Step 3: Add Context to Errors

```typescript
// src/middleware/sentry-context.ts
import * as Sentry from "@sentry/node";

export function sentryUserContext(req: Request, res: Response, next: NextFunction) {
  if (req.user) {
    Sentry.setUser({
      id: req.user.id,
      email: req.user.email,
      // Don't send PII you don't need
    });

    Sentry.setTag("org_id", req.user.orgId);
    Sentry.setTag("plan", req.user.plan);
  }
  next();
}
```

```typescript
// In your API handlers — add breadcrumbs for debugging context
import * as Sentry from "@sentry/node";

async function processOrder(orderId: string) {
  Sentry.addBreadcrumb({
    category: "order",
    message: `Processing order ${orderId}`,
    level: "info",
  });

  const order = await db.order.findUnique({ where: { id: orderId } });
  if (!order) throw new Error(`Order not found: ${orderId}`);

  Sentry.setContext("order", {
    id: order.id,
    total: order.total,
    itemCount: order.items.length,
    status: order.status,
  });

  // If this throws, Sentry captures all the breadcrumbs and context above
  await chargePayment(order);
}
```

## Step 4: Release Tracking in CI

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - run: npm ci && npm run build

      - name: Create Sentry release
        uses: getsentry/action-release@v1
        env:
          SENTRY_AUTH_TOKEN: ${{ secrets.SENTRY_AUTH_TOKEN }}
          SENTRY_ORG: ${{ secrets.SENTRY_ORG }}
          SENTRY_PROJECT: my-app
        with:
          environment: production
          sourcemaps: .next
          version: ${{ github.sha }}

      # Deploy step here...
```

## Step 5: Custom Error Boundaries

```tsx
// src/components/ErrorBoundary.tsx
"use client";
import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function ErrorPage({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
      <h2 className="text-xl font-semibold">Something went wrong</h2>
      <p className="text-gray-500">Our team has been notified and is looking into it.</p>
      <div className="flex gap-3">
        <button onClick={reset} className="px-4 py-2 bg-blue-600 text-white rounded">
          Try again
        </button>
        <button
          onClick={() => Sentry.showReportDialog()}
          className="px-4 py-2 border rounded"
        >
          Report feedback
        </button>
      </div>
    </div>
  );
}
```

## Step 6: Alert Configuration

```typescript
// In Sentry dashboard, set up alert rules:
// 1. New issue alert → Slack #bugs channel (immediate)
// 2. Issue frequency > 10/hour → PagerDuty (critical)
// 3. Transaction P95 > 3s → Slack #performance (warning)
// 4. Crash-free rate < 95% → Email team leads

// Or via sentry-cli:
// sentry-cli alerts create --name "High Error Rate" \
//   --condition "events_seen > 50 in 1h" \
//   --action "slack:#alerts"
```

## Summary

Oleg's team now catches errors within seconds of deployment. Every error in Sentry shows: the full stack trace, which release introduced it, which user hit it, what they were doing (breadcrumbs), and a session replay video of their screen. Release tracking ties errors to specific deploys, so they know which commit caused a regression. The feedback widget lets users report issues with one click, and the report includes the error context automatically. They went from "I think something's broken" to "We fixed it before anyone noticed" in one sprint.
