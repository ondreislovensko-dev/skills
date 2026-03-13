---
title: "Build a Multi-Channel Notification System with AI"
slug: build-notification-system
description: "Design and implement a notification system supporting email, push, and in-app channels with user preferences and delivery tracking."
skills: [notification-system, template-engine]
category: development
tags: [notifications, email, push-notifications, in-app, messaging]
---

# Build a Multi-Channel Notification System with AI

## The Problem

Raj's project management SaaS has a notification problem that is costing users. Deadline reminders only go to the in-app feed -- if a user is not staring at the dashboard, they miss them. Meanwhile, every single comment on every task triggers an email, and the unsubscribe rate hit 8% last month. Users are either missing critical alerts or drowning in noise, and there is no middle ground because there are no preferences.

The codebase makes it worse: 12 different places send notifications with no central routing. The password reset email is in `auth/reset.ts`. Comment notifications live in `tasks/comments.ts`. The weekly digest is a standalone cron job. Each one talks directly to SendGrid or pushes to a WebSocket. There is no consistency, no retry logic, and when the push notification provider has an outage, messages silently disappear.

Raj needs a single notification pipeline: one place where every notification enters, gets routed to the right channels based on user preferences, renders consistently across email, push, and in-app, and tracks whether it actually arrived.

## The Solution

Use the **notification-system** skill to architect the delivery pipeline with channel routing and preference management, and the **template-engine** skill to create consistent notification templates across all channels.

## Step-by-Step Walkthrough

### Step 1: Inventory Every Notification in the Codebase

```text
Analyze my application in src/ and identify all places where we notify users. Group them into notification types: transactional (password reset, email verification, order confirmation), activity (new comment, mention, follower), and marketing (weekly digest, feature announcement). For each type, recommend which channels to use (email, push, in-app) and the default user preference.
```

A scan of the codebase reveals 8 notification types scattered across 12 files:

| Notification | Type | Channels | Default | Can Disable? |
|---|---|---|---|---|
| Password reset | Transactional | Email | Always on | No |
| Email verification | Transactional | Email | Always on | No |
| Order confirmation | Transactional | Email + in-app | Both on | No |
| New comment | Activity | Push + in-app | Both on | Yes |
| Mention | Activity | Push + in-app | Both on | Yes |
| New follower | Activity | In-app only | On | Yes |
| Weekly digest | Marketing | Email | On | Yes |
| Feature announcement | Marketing | Email + in-app | On | Yes |

The two transactional types should never be disableable -- a user who turns off password reset emails is locked out of their account. Everything else needs a preference toggle.

### Step 2: Build the Notification Router

```text
Create a notification service with these components: a NotificationRouter that accepts a notification event and routes it to the correct channels based on user preferences, channel-specific adapters for email (via SendGrid), push (via Firebase Cloud Messaging), and in-app (via PostgreSQL + WebSocket), a preference store in PostgreSQL, and a retry queue using a job system. Use TypeScript and make the adapters pluggable so we can swap providers later.
```

The architecture is intentionally simple: every notification enters through one function, gets checked against user preferences, and fans out to the appropriate channel adapters.

```typescript
// src/notifications/router.ts

interface NotificationEvent {
  type: 'password-reset' | 'new-comment' | 'mention' | /* ... */;
  userId: string;
  data: Record<string, unknown>;
}

async function notify(event: NotificationEvent): Promise<void> {
  const preferences = await getPreferences(event.userId);
  const channels = resolveChannels(event.type, preferences);

  for (const channel of channels) {
    const rendered = await renderTemplate(event.type, channel, event.data);
    await enqueueDelivery(channel, event.userId, rendered);
  }
}
```

Channel adapters implement a common interface so swapping SendGrid for Postmark or FCM for OneSignal means changing one file:

```typescript
// src/notifications/channels/email.ts
export class SendGridAdapter implements ChannelAdapter {
  async send(userId: string, content: RenderedContent): Promise<DeliveryResult> {
    // SendGrid API call
  }
}

// src/notifications/channels/push.ts
export class FCMAdapter implements ChannelAdapter {
  async send(userId: string, content: RenderedContent): Promise<DeliveryResult> {
    // Firebase Cloud Messaging call
  }
}
```

### Step 3: Create Multi-Format Templates

```text
Using the template engine, create templates for all 8 notification types. Each template should render for three formats: email (HTML with inline CSS), push (title + body limited to 178 characters), and in-app (short message with action URL). Use a shared data schema per notification type so one event triggers consistent content across all channels.
```

One notification event, three different renderings. The same "new comment" event produces:

- **Email**: Full HTML with the comment preview, commenter's avatar, and a "View Comment" button
- **Push**: "Alex commented: 'Great analysis of the...'" -- truncated at 178 characters with a proper ellipsis
- **In-app**: Short message with an action URL that deep-links to the comment

Each template shares a typed data interface so the content stays consistent:

```typescript
interface NewCommentData {
  commenterName: string;
  commenterAvatar: string;
  commentPreview: string;   // first 200 chars
  taskTitle: string;
  taskUrl: string;
}
```

The email template uses inline CSS (because email clients ignore external stylesheets). The push template has hard character limits. The in-app template is a short markdown string. All three are generated from the same event data.

### Step 4: Implement User Preference Management

```text
Create a preferences API with endpoints: GET /api/notifications/preferences (returns current settings), PATCH /api/notifications/preferences (updates channel toggles per notification type), and POST /api/notifications/unsubscribe/:token (one-click email unsubscribe per CAN-SPAM). Include a React component that renders the preference matrix as a table with toggles. Transactional notifications should show as locked/always-on.
```

The preference UI renders as a matrix: notification types down the left, channels across the top, toggles at each intersection. Transactional rows are greyed out with a lock icon -- users can see them but cannot disable them.

The one-click unsubscribe endpoint is legally required by CAN-SPAM. Every marketing and activity email includes an unsubscribe link with a signed token. Clicking it disables that notification type's email channel without requiring login.

### Step 5: Add Delivery Tracking and Retry Logic

```text
Add delivery tracking to the notification system. Store delivery status (queued, sent, delivered, failed, read) in PostgreSQL. Implement retry with exponential backoff: 3 retries for email (1min, 5min, 30min), 2 retries for push (30s, 2min), no retry for in-app. Add a dead letter queue for permanently failed notifications. Create a monitoring query that shows delivery success rates by channel and notification type for the last 7 days.
```

Every notification gets a row in the `deliveries` table tracking its lifecycle:

| Status | Meaning |
|---|---|
| `queued` | Entered the pipeline, waiting for delivery |
| `sent` | Handed off to the provider (SendGrid, FCM) |
| `delivered` | Provider confirmed delivery (webhook callback) |
| `failed` | Delivery failed, will retry |
| `dead` | All retries exhausted, moved to dead letter queue |
| `read` | User opened/clicked (tracked via pixel or webhook) |

Retry schedules are channel-specific because failure modes differ. Email bounces are usually permanent (bad address), so retries are spaced further apart. Push failures are often transient (device offline), so retries are faster but fewer.

A monitoring query surfaces problems before users complain:

```sql
SELECT
  notification_type,
  channel,
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE status = 'delivered') AS delivered,
  ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'delivered') / COUNT(*), 1) AS success_rate
FROM deliveries
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY notification_type, channel
ORDER BY success_rate ASC;
```

## Real-World Example

Raj consolidates all 12 notification paths into a single pipeline in two days. Templates go live the same week -- push notifications are properly truncated for the first time, and every email finally has an unsubscribe link.

The preference UI launches the following Monday. Within a week, users fine-tune their settings instead of unsubscribing entirely. Email unsubscribe rates drop from 8% to under 1%. Deadline reminders now default to email and push, so users stop missing them.

The real payoff comes from delivery tracking. The monitoring query reveals that their push notification provider has a 12% failure rate on Android -- something that had been silently dropping messages for months. Because the adapters are pluggable, swapping to a different provider takes an afternoon. Complaints about missed notifications drop by 80% in the first week.
