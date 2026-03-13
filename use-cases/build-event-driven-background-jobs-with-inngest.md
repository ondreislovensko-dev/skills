---
title: Build Event-Driven Background Jobs with Inngest
slug: build-event-driven-background-jobs-with-inngest
description: >-
  Replace fragile cron jobs and queue workers with Inngest's durable functions
  for reliable background processing — handle webhooks, send drip emails,
  process uploads, and orchestrate multi-step workflows with automatic retries.
skills:
  - inngest
  - resend
  - sharp
  - redis
  - stripe-webhooks
category: development
tags:
  - background-jobs
  - event-driven
  - serverless
  - typescript
  - workflows
---

# Build Event-Driven Background Jobs with Inngest

Marco's SaaS has background work scattered everywhere: a cron job that sends weekly digest emails, a webhook handler that processes Stripe events inline (and times out), an image upload that blocks the API for 10 seconds while resizing. He's lost revenue from failed Stripe webhooks and users complain about slow uploads. He needs reliable background processing without managing Redis queues, dead letter queues, or worker processes.

## Step 1: Set Up Inngest

```bash
npm install inngest
npx inngest-cli@latest dev  # Local dev server at localhost:8288
```

```typescript
// src/inngest/client.ts
import { Inngest } from "inngest";

export const inngest = new Inngest({
  id: "my-saas-app",
  schemas: new EventSchemas().fromRecord<{
    "user/signup.completed": { data: { userId: string; email: string; plan: string } };
    "invoice/payment.received": { data: { customerId: string; amount: number; invoiceId: string } };
    "file/upload.completed": { data: { fileId: string; userId: string; url: string; mimeType: string } };
    "digest/weekly.trigger": { data: { batchId: string } };
  }>(),
});
```

## Step 2: Onboarding Drip Email Sequence

```typescript
// src/inngest/functions/onboarding-emails.ts
import { inngest } from "../client";
import { Resend } from "resend";

const resend = new Resend(process.env.RESEND_API_KEY);

export const onboardingDrip = inngest.createFunction(
  { id: "onboarding-drip-emails", concurrency: { limit: 10 } },
  { event: "user/signup.completed" },
  async ({ event, step }) => {
    // Welcome email — immediately
    await step.run("send-welcome-email", async () => {
      await resend.emails.send({
        from: "hello@yourapp.com",
        to: event.data.email,
        subject: "Welcome to YourApp!",
        html: renderWelcomeEmail(event.data),
      });
    });

    // Wait 1 day, then send tips email
    await step.sleep("wait-1-day", "1d");

    const user = await step.run("check-user-activity", async () => {
      return await db.user.findUnique({
        where: { id: event.data.userId },
        select: { projectCount: true, lastActiveAt: true },
      });
    });

    if (user && user.projectCount === 0) {
      await step.run("send-getting-started-tips", async () => {
        await resend.emails.send({
          from: "hello@yourapp.com",
          to: event.data.email,
          subject: "3 things to try in YourApp",
          html: renderTipsEmail(event.data),
        });
      });
    }

    // Wait 3 more days
    await step.sleep("wait-3-days", "3d");

    await step.run("send-checkin-email", async () => {
      await resend.emails.send({
        from: "hello@yourapp.com",
        to: event.data.email,
        subject: "How's it going?",
        html: renderCheckinEmail(event.data),
      });
    });
  }
);
```

## Step 3: Reliable Stripe Webhook Processing

```typescript
// src/inngest/functions/stripe-webhooks.ts
export const processPayment = inngest.createFunction(
  {
    id: "process-stripe-payment",
    retries: 5,
    concurrency: { limit: 5, key: "event.data.customerId" },
  },
  { event: "invoice/payment.received" },
  async ({ event, step }) => {
    // Each step is individually retried and checkpointed
    const subscription = await step.run("update-subscription", async () => {
      return await db.subscription.update({
        where: { stripeCustomerId: event.data.customerId },
        data: { status: "active", lastPaymentAt: new Date() },
      });
    });

    await step.run("generate-invoice-pdf", async () => {
      const pdf = await generateInvoicePdf(event.data.invoiceId);
      await uploadToS3(`invoices/${event.data.invoiceId}.pdf`, pdf);
    });

    await step.run("send-receipt", async () => {
      await resend.emails.send({
        from: "billing@yourapp.com",
        to: subscription.email,
        subject: `Receipt for $${(event.data.amount / 100).toFixed(2)}`,
        attachments: [{ path: `invoices/${event.data.invoiceId}.pdf` }],
      });
    });

    await step.run("update-analytics", async () => {
      await analytics.track("payment_received", {
        amount: event.data.amount,
        customerId: event.data.customerId,
      });
    });
  }
);
```

## Step 4: Image Processing Pipeline

```typescript
// src/inngest/functions/image-processing.ts
import sharp from "sharp";

export const processUploadedImage = inngest.createFunction(
  { id: "process-uploaded-image", retries: 3 },
  { event: "file/upload.completed" },
  async ({ event, step }) => {
    if (!event.data.mimeType.startsWith("image/")) return;

    const originalBuffer = await step.run("download-original", async () => {
      const response = await fetch(event.data.url);
      return Buffer.from(await response.arrayBuffer());
    });

    // Generate multiple sizes in parallel using step.run
    const sizes = [
      { name: "thumb", width: 150, height: 150 },
      { name: "medium", width: 800, height: 600 },
      { name: "large", width: 1920, height: 1080 },
    ];

    for (const size of sizes) {
      await step.run(`resize-${size.name}`, async () => {
        const resized = await sharp(originalBuffer)
          .resize(size.width, size.height, { fit: "inside", withoutEnlargement: true })
          .webp({ quality: 80 })
          .toBuffer();

        await uploadToS3(`files/${event.data.fileId}/${size.name}.webp`, resized);
      });
    }

    await step.run("update-file-record", async () => {
      await db.file.update({
        where: { id: event.data.fileId },
        data: {
          processed: true,
          variants: sizes.map((s) => `files/${event.data.fileId}/${s.name}.webp`),
        },
      });
    });
  }
);
```

## Step 5: Wire Up the API Route

```typescript
// src/app/api/inngest/route.ts (Next.js App Router)
import { serve } from "inngest/next";
import { inngest } from "@/inngest/client";
import { onboardingDrip } from "@/inngest/functions/onboarding-emails";
import { processPayment } from "@/inngest/functions/stripe-webhooks";
import { processUploadedImage } from "@/inngest/functions/image-processing";

export const { GET, POST, PUT } = serve({
  client: inngest,
  functions: [onboardingDrip, processPayment, processUploadedImage],
});
```

## Summary

Marco replaced three fragile systems with one: Inngest handles his onboarding email drip (with smart delays and user-activity checks), processes Stripe webhooks reliably with automatic retries on each step, and resizes uploaded images in the background. Each step is durable — if the server restarts mid-function, it picks up where it left off. No Redis to manage, no worker processes to monitor, no dead letter queues to drain. Failed steps retry individually without re-running the entire function.
