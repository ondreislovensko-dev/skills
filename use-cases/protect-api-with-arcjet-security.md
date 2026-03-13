---
title: Protect Your API with Arcjet Security
slug: protect-api-with-arcjet-security
description: >-
  Add production-grade API protection with Arcjet — rate limiting, bot
  detection, email validation, and attack prevention as code, integrated
  directly into your Next.js or Express application.
skills:
  - arcjet
  - authjs
category: security
tags:
  - security
  - rate-limiting
  - bot-detection
  - api-protection
  - typescript
---

# Protect Your API with Arcjet Security

Liam's API is getting hammered: bots scraping his content, credential stuffing attacks on login, fake signups from disposable emails, and one customer's buggy script making 10,000 requests per minute. He needs multi-layered protection that works in his existing codebase — not a separate WAF or reverse proxy to configure. Arcjet runs as middleware in his app with rate limiting, bot detection, and email validation as code.

## Step 1: Install and Configure

```bash
npm install @arcjet/next  # or @arcjet/node for Express
```

```typescript
// src/lib/arcjet.ts
import arcjet, { shield, detectBot, tokenBucket, validateEmail, fixedWindow } from "@arcjet/next";

export const aj = arcjet({
  key: process.env.ARCJET_KEY!,
  characteristics: ["ip.src"],
  rules: [
    // Shield: protect against common attacks (SQLi, XSS, etc.)
    shield({ mode: "LIVE" }),
    // Bot detection: block automated requests
    detectBot({
      mode: "LIVE",
      allow: [
        "CATEGORY:SEARCH_ENGINE",  // Allow Google, Bing
        "CATEGORY:MONITOR",         // Allow uptime monitors
      ],
    }),
  ],
});
```

## Step 2: Rate Limit API Endpoints

```typescript
// src/app/api/data/route.ts
import { aj } from "@/lib/arcjet";
import { tokenBucket } from "@arcjet/next";
import { NextRequest, NextResponse } from "next/server";

const rateLimited = aj.withRule(
  tokenBucket({
    mode: "LIVE",
    refillRate: 10,     // 10 tokens per interval
    interval: 60,       // per 60 seconds
    capacity: 20,       // burst up to 20
  })
);

export async function GET(req: NextRequest) {
  const decision = await rateLimited.protect(req);

  if (decision.isDenied()) {
    return NextResponse.json(
      { error: "Too many requests", retryAfter: decision.reason.resetTime },
      {
        status: 429,
        headers: {
          "Retry-After": String(Math.ceil((decision.reason.resetTime || 60000) / 1000)),
        },
      }
    );
  }

  // Process request normally
  const data = await fetchData();
  return NextResponse.json(data);
}
```

## Step 3: Protect Login with Strict Rate Limiting

```typescript
// src/app/api/auth/login/route.ts
import { aj } from "@/lib/arcjet";
import { fixedWindow, detectBot } from "@arcjet/next";

const loginProtection = aj.withRule(
  fixedWindow({
    mode: "LIVE",
    window: "5m",
    max: 5,  // 5 attempts per 5 minutes per IP
    characteristics: ["ip.src"],
  })
).withRule(
  detectBot({ mode: "LIVE", allow: [] })  // No bots allowed on login
);

export async function POST(req: NextRequest) {
  const decision = await loginProtection.protect(req);

  if (decision.isDenied()) {
    if (decision.reason.isRateLimit()) {
      return NextResponse.json(
        { error: "Too many login attempts. Try again in 5 minutes." },
        { status: 429 }
      );
    }
    if (decision.reason.isBot()) {
      return NextResponse.json({ error: "Automated requests not allowed" }, { status: 403 });
    }
    return NextResponse.json({ error: "Request blocked" }, { status: 403 });
  }

  const { email, password } = await req.json();
  // ... authenticate user
}
```

## Step 4: Email Validation on Signup

```typescript
// src/app/api/auth/signup/route.ts
import { aj } from "@/lib/arcjet";
import { validateEmail, fixedWindow } from "@arcjet/next";

const signupProtection = aj.withRule(
  validateEmail({
    mode: "LIVE",
    block: [
      "DISPOSABLE",     // Block temp emails (guerrillamail, etc.)
      "INVALID",        // Block invalid format
      "NO_MX_RECORDS",  // Block domains without mail servers
    ],
  })
).withRule(
  fixedWindow({ mode: "LIVE", window: "1h", max: 3 })  // 3 signups per hour per IP
);

export async function POST(req: NextRequest) {
  const { email, password, name } = await req.json();

  const decision = await signupProtection.protect(req, { email });

  if (decision.isDenied()) {
    if (decision.reason.isEmail()) {
      const emailType = decision.reason.emailTypes;
      if (emailType.includes("DISPOSABLE")) {
        return NextResponse.json({ error: "Disposable email addresses are not allowed" }, { status: 400 });
      }
      return NextResponse.json({ error: "Invalid email address" }, { status: 400 });
    }
    return NextResponse.json({ error: "Too many signup attempts" }, { status: 429 });
  }

  // ... create user
}
```

## Step 5: Per-User Rate Limiting for Authenticated Routes

```typescript
// src/middleware.ts
import { aj } from "@/lib/arcjet";
import { tokenBucket } from "@arcjet/next";
import { NextResponse, type NextRequest } from "next/server";

const apiProtection = aj.withRule(
  tokenBucket({
    mode: "LIVE",
    refillRate: 60,
    interval: 60,
    capacity: 120,
    // Rate limit by user ID for authenticated requests, IP for anonymous
    characteristics: ["userId"],
  })
);

export async function middleware(req: NextRequest) {
  const userId = req.headers.get("x-user-id") || req.ip || "anonymous";

  const decision = await apiProtection.protect(req, { userId });

  if (decision.isDenied()) {
    return NextResponse.json({ error: "Rate limit exceeded" }, { status: 429 });
  }

  // Add security headers
  const response = NextResponse.next();
  response.headers.set("X-RateLimit-Remaining", String(decision.reason.remaining || 0));
  return response;
}

export const config = {
  matcher: "/api/:path*",
};
```

## Summary

Liam's API is now protected at multiple layers: Shield blocks common attack patterns (SQLi, XSS payloads in headers), bot detection stops scrapers while allowing search engines, rate limiting prevents abuse with different limits for different endpoints (strict on login, generous on reads), and email validation blocks fake signups from disposable addresses. Everything is defined as code in his TypeScript codebase — no external WAF dashboard to configure. When a request is blocked, Arcjet returns structured reasons so he can show appropriate error messages. The credential stuffing attacks stopped, fake signups dropped 95%, and the rogue customer's script gets rate-limited instead of taking down the API.
