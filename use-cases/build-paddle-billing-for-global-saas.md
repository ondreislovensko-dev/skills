---
title: Build Paddle Billing for a Global SaaS
slug: build-paddle-billing-for-global-saas
description: >-
  Implement Paddle as your merchant of record for a SaaS — handle global
  tax compliance automatically, manage subscriptions, process webhooks,
  and build a self-service billing portal without becoming a tax expert.
skills:
  - paddle
  - drizzle-orm
category: business
tags:
  - billing
  - paddle
  - saas
  - payments
  - subscriptions
---

# Build Paddle Billing for a Global SaaS

Finn's SaaS sells to customers in 40 countries. With Stripe, he's the merchant of record — responsible for collecting and remitting VAT, GST, and sales tax in every jurisdiction. He got a €15,000 tax bill from the EU because he wasn't handling VAT correctly. Paddle is a merchant of record: they handle all tax collection, compliance, and remittance. Finn receives net payouts and never thinks about tax again.

## Step 1: Set Up Paddle SDK

```bash
npm install @paddle/paddle-node-sdk
```

```typescript
// src/lib/paddle.ts
import Paddle from "@paddle/paddle-node-sdk";

export const paddle = new Paddle.Paddle(process.env.PADDLE_API_KEY!);

// Product and price IDs from Paddle dashboard
export const PRICES = {
  pro_monthly: "pri_01abc123monthly",
  pro_annual: "pri_01abc123annual",
  enterprise_monthly: "pri_01xyz789monthly",
  enterprise_annual: "pri_01xyz789annual",
} as const;
```

## Step 2: Client-Side Checkout with Paddle.js

```tsx
// src/components/PricingPage.tsx
"use client";
import { initializePaddle, Paddle } from "@paddle/paddle-js";
import { useEffect, useState } from "react";

export function PricingPage({ userId, email }: { userId: string; email: string }) {
  const [paddle, setPaddle] = useState<Paddle>();

  useEffect(() => {
    initializePaddle({
      environment: process.env.NODE_ENV === "production" ? "production" : "sandbox",
      token: process.env.NEXT_PUBLIC_PADDLE_CLIENT_TOKEN!,
    }).then(setPaddle);
  }, []);

  const handleCheckout = (priceId: string) => {
    paddle?.Checkout.open({
      items: [{ priceId, quantity: 1 }],
      customer: { email },
      customData: { userId },
      settings: {
        displayMode: "overlay",
        theme: "light",
        successUrl: `${window.location.origin}/dashboard/billing?success=true`,
      },
    });
  };

  return (
    <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto p-8">
      <div className="border rounded-xl p-6">
        <h2 className="text-xl font-bold">Pro</h2>
        <p className="text-3xl font-bold mt-2">$29<span className="text-lg text-gray-500">/mo</span></p>
        <p className="text-sm text-gray-500 mt-1">Billed monthly, cancel anytime</p>
        <ul className="mt-4 space-y-2 text-sm">
          <li>✓ Unlimited projects</li>
          <li>✓ 10 team members</li>
          <li>✓ Priority support</li>
        </ul>
        <button
          onClick={() => handleCheckout("pri_01abc123monthly")}
          className="w-full mt-6 py-2 bg-blue-600 text-white rounded-lg"
        >
          Subscribe to Pro
        </button>
      </div>

      <div className="border-2 border-blue-600 rounded-xl p-6">
        <h2 className="text-xl font-bold">Enterprise</h2>
        <p className="text-3xl font-bold mt-2">$99<span className="text-lg text-gray-500">/mo</span></p>
        <p className="text-sm text-gray-500 mt-1">Billed monthly, includes tax compliance</p>
        <ul className="mt-4 space-y-2 text-sm">
          <li>✓ Everything in Pro</li>
          <li>✓ Unlimited team members</li>
          <li>✓ SSO & audit logs</li>
          <li>✓ Dedicated support</li>
        </ul>
        <button
          onClick={() => handleCheckout("pri_01xyz789monthly")}
          className="w-full mt-6 py-2 bg-blue-600 text-white rounded-lg"
        >
          Subscribe to Enterprise
        </button>
      </div>
    </div>
  );
}
```

## Step 3: Webhook Processing

```typescript
// src/app/api/paddle/webhook/route.ts
import { NextRequest } from "next/server";
import Paddle from "@paddle/paddle-node-sdk";
import { db } from "@/db";
import { users, subscriptions } from "@/db/schema";
import { eq } from "drizzle-orm";

const paddle = new Paddle.Paddle(process.env.PADDLE_API_KEY!);

export async function POST(req: NextRequest) {
  const signature = req.headers.get("paddle-signature");
  const body = await req.text();

  // Verify webhook signature
  const event = paddle.webhooks.unmarshal(body, process.env.PADDLE_WEBHOOK_SECRET!, signature!);
  if (!event) return new Response("Invalid signature", { status: 401 });

  switch (event.eventType) {
    case "subscription.created": {
      const sub = event.data;
      const userId = sub.customData?.userId as string;
      const plan = sub.items[0].price.id.includes("enterprise") ? "enterprise" : "pro";

      await db.insert(subscriptions).values({
        id: sub.id,
        userId,
        paddleSubscriptionId: sub.id,
        paddleCustomerId: sub.customerId,
        plan,
        status: sub.status,
        currentPeriodEnd: new Date(sub.currentBillingPeriod.endsAt),
      });

      await db.update(users).set({ plan }).where(eq(users.id, userId));
      break;
    }

    case "subscription.updated": {
      const sub = event.data;
      await db.update(subscriptions).set({
        status: sub.status,
        currentPeriodEnd: new Date(sub.currentBillingPeriod.endsAt),
      }).where(eq(subscriptions.paddleSubscriptionId, sub.id));
      break;
    }

    case "subscription.canceled": {
      const sub = event.data;
      await db.update(subscriptions).set({ status: "canceled" })
        .where(eq(subscriptions.paddleSubscriptionId, sub.id));

      // Downgrade to free when period ends
      const dbSub = await db.query.subscriptions.findFirst({
        where: eq(subscriptions.paddleSubscriptionId, sub.id),
      });
      if (dbSub) {
        await db.update(users).set({ plan: "free" }).where(eq(users.id, dbSub.userId));
      }
      break;
    }

    case "transaction.completed": {
      // Payment successful — invoice available
      console.log(`Payment completed: ${event.data.id}`);
      break;
    }
  }

  return new Response("OK");
}
```

## Step 4: Subscription Management

```typescript
// src/lib/billing.ts
import { paddle, PRICES } from "./paddle";

export async function getSubscription(paddleSubscriptionId: string) {
  return paddle.subscriptions.get(paddleSubscriptionId);
}

export async function cancelSubscription(paddleSubscriptionId: string) {
  return paddle.subscriptions.cancel(paddleSubscriptionId, {
    effectiveFrom: "next_billing_period",
  });
}

export async function updatePlan(paddleSubscriptionId: string, newPriceId: string) {
  const sub = await paddle.subscriptions.get(paddleSubscriptionId);
  return paddle.subscriptions.update(paddleSubscriptionId, {
    items: [{ priceId: newPriceId, quantity: 1 }],
    prorationBillingMode: "prorated_immediately",
  });
}

export async function getPortalUrl(paddleSubscriptionId: string) {
  // Paddle provides a hosted customer portal for managing billing
  const sub = await paddle.subscriptions.get(paddleSubscriptionId);
  return sub.managementUrls?.updatePaymentMethod;
}
```

## Summary

Finn never thinks about tax again. Paddle collects VAT in the EU, GST in Australia, sales tax in US states — all handled automatically because Paddle is the merchant of record. The checkout overlay handles localized pricing (shows € in Europe, £ in UK), supports 30+ payment methods, and generates compliant invoices. Webhooks keep his database in sync with subscription state. The customer portal lets users update their payment method and download invoices without Finn building any UI. He receives net payouts every month — Paddle's cut is 5% + $0.50, but that's cheaper than the accountant he'd need for multi-country tax compliance.
