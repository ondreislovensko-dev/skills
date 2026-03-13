---
title: Build Privacy-First Analytics for Your SaaS
slug: build-privacy-first-analytics-for-saas
description: >-
  Replace Google Analytics with a self-hosted, GDPR-compliant analytics stack
  using Umami or Plausible, track custom events, build conversion funnels, and
  create an internal dashboard with Grafana.
skills:
  - umami
  - plausible
  - grafana
  - docker-compose
  - nginx
category: analytics
tags:
  - analytics
  - privacy
  - gdpr
  - self-hosted
  - saas
---

# Build Privacy-First Analytics for Your SaaS

Kira runs a B2B SaaS and her enterprise customers keep asking about GDPR compliance. Google Analytics collects personal data, requires cookie banners, and sends everything to Google's servers. She wants to self-host analytics that respect user privacy, track the metrics she actually cares about (signups, feature adoption, churn signals), and feed that data into an internal dashboard her team can use — all without cookie banners.

## Step 1: Deploy Umami with Docker Compose

```yaml
# docker-compose.yml
version: "3"
services:
  umami:
    image: ghcr.io/umami-software/umami:postgresql-latest
    ports:
      - "3000:3000"
    environment:
      DATABASE_URL: postgresql://umami:${DB_PASSWORD}@db:5432/umami
      APP_SECRET: ${APP_SECRET}
    depends_on:
      db:
        condition: service_healthy
    restart: always

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: umami
      POSTGRES_USER: umami
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - umami-db:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U umami"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  umami-db:
```

```bash
# Generate secrets and start
echo "DB_PASSWORD=$(openssl rand -hex 24)" > .env
echo "APP_SECRET=$(openssl rand -hex 32)" >> .env
docker compose up -d
```

## Step 2: Add Tracking Script to Your App

```typescript
// src/components/Analytics.tsx — No cookies, no consent banner needed
export function Analytics() {
  if (process.env.NODE_ENV !== "production") return null;

  return (
    <script
      defer
      src="https://analytics.yourapp.com/script.js"
      data-website-id={process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID}
    />
  );
}
```

```typescript
// src/lib/analytics.ts — Custom event tracking
export function trackEvent(eventName: string, data?: Record<string, string | number>) {
  if (typeof window !== "undefined" && window.umami) {
    window.umami.track(eventName, data);
  }
}

// Usage in your app:
trackEvent("signup_completed", { plan: "pro", source: "landing-page" });
trackEvent("feature_used", { feature: "export-csv", count: 1 });
trackEvent("upgrade_clicked", { from: "free", to: "team" });
```

## Step 3: Track Conversion Funnels

```typescript
// src/hooks/useFunnelTracking.ts — Track user journey through signup
import { trackEvent } from "@/lib/analytics";

const FUNNEL_STEPS = [
  "visited_pricing",
  "clicked_signup",
  "entered_email",
  "verified_email",
  "completed_onboarding",
  "first_project_created",
] as const;

export function useFunnelTracking() {
  const trackStep = (step: (typeof FUNNEL_STEPS)[number], meta?: Record<string, string>) => {
    trackEvent(`funnel:${step}`, {
      ...meta,
      timestamp: new Date().toISOString(),
    });
  };

  return { trackStep };
}
```

## Step 4: Export Data to Grafana for Internal Dashboards

```bash
# Add Grafana to your docker-compose.yml
# Then configure PostgreSQL as a data source pointing to Umami's database
```

```sql
-- Grafana query: Daily active users over time
SELECT
  date_trunc('day', created_at) AS time,
  COUNT(DISTINCT session_id) AS daily_active_users
FROM website_event
WHERE website_id = '${website_id}'
  AND created_at >= NOW() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1;
```

```sql
-- Grafana query: Conversion funnel
SELECT
  event_name,
  COUNT(DISTINCT session_id) AS unique_users
FROM website_event
WHERE event_name LIKE 'funnel:%'
  AND created_at >= NOW() - INTERVAL '7 days'
GROUP BY event_name
ORDER BY
  CASE event_name
    WHEN 'funnel:visited_pricing' THEN 1
    WHEN 'funnel:clicked_signup' THEN 2
    WHEN 'funnel:entered_email' THEN 3
    WHEN 'funnel:verified_email' THEN 4
    WHEN 'funnel:completed_onboarding' THEN 5
    WHEN 'funnel:first_project_created' THEN 6
  END;
```

## Step 5: Configure Nginx Reverse Proxy with SSL

```nginx
# /etc/nginx/sites-available/analytics
server {
    listen 443 ssl http2;
    server_name analytics.yourapp.com;

    ssl_certificate /etc/letsencrypt/live/analytics.yourapp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/analytics.yourapp.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Summary

Kira now has privacy-first analytics that her enterprise customers love. No cookie banners needed — Umami doesn't use cookies or collect personal data. She tracks signups, feature usage, and conversion funnels with custom events, and her team monitors everything on a Grafana dashboard. The entire stack is self-hosted, GDPR-compliant by design, and costs $5/month on a VPS instead of $150/month for a commercial analytics tool.
