---
title: Build a Redis Caching Layer for Your API
slug: build-redis-caching-layer-for-api
description: >-
  Add intelligent caching to your API with Redis — implement cache-aside
  pattern, cache invalidation, rate limiting, session storage, and real-time
  leaderboards to reduce database load by 90%.
skills:
  - redis
  - drizzle-orm
  - neon
category: infrastructure
tags:
  - caching
  - redis
  - performance
  - api
  - database
---

# Build a Redis Caching Layer for Your API

Raj's API serves 10,000 requests per minute but his PostgreSQL database is struggling. Most requests hit the same data — user profiles, product listings, team settings — that changes infrequently. He needs caching that's simple to implement, handles invalidation correctly (no stale data bugs), and also handles rate limiting and session storage since he's adding Redis anyway.

## Step 1: Redis Client with Connection Pooling

```typescript
// src/lib/redis.ts
import { Redis } from "ioredis";

export const redis = new Redis(process.env.REDIS_URL!, {
  maxRetriesPerRequest: 3,
  retryStrategy: (times) => Math.min(times * 100, 3000),
  enableReadyCheck: true,
  lazyConnect: false,
});

redis.on("error", (err) => console.error("Redis error:", err));
redis.on("connect", () => console.log("Redis connected"));
```

## Step 2: Cache-Aside Pattern with Type Safety

```typescript
// src/lib/cache.ts
import { redis } from "./redis";

interface CacheOptions {
  ttl: number;          // seconds
  staleWhileRevalidate?: number;  // serve stale, refresh in background
}

export async function cached<T>(
  key: string,
  fetcher: () => Promise<T>,
  options: CacheOptions
): Promise<T> {
  const raw = await redis.get(key);

  if (raw) {
    const { data, expiresAt } = JSON.parse(raw);

    // Fresh — return immediately
    if (Date.now() < expiresAt) return data as T;

    // Stale but within revalidation window — return stale, refresh in background
    if (options.staleWhileRevalidate) {
      const staleDeadline = expiresAt + options.staleWhileRevalidate * 1000;
      if (Date.now() < staleDeadline) {
        refreshInBackground(key, fetcher, options);
        return data as T;
      }
    }
  }

  // Cache miss or fully expired
  const data = await fetcher();
  await redis.setex(
    key,
    options.ttl + (options.staleWhileRevalidate || 0),
    JSON.stringify({ data, expiresAt: Date.now() + options.ttl * 1000 })
  );
  return data;
}

async function refreshInBackground<T>(key: string, fetcher: () => Promise<T>, options: CacheOptions) {
  // Use a lock to prevent thundering herd
  const lockKey = `lock:${key}`;
  const acquired = await redis.set(lockKey, "1", "EX", 10, "NX");
  if (!acquired) return;

  try {
    const data = await fetcher();
    await redis.setex(
      key,
      options.ttl + (options.staleWhileRevalidate || 0),
      JSON.stringify({ data, expiresAt: Date.now() + options.ttl * 1000 })
    );
  } finally {
    await redis.del(lockKey);
  }
}
```

## Step 3: Smart Cache Invalidation

```typescript
// src/lib/cache-invalidation.ts
import { redis } from "./redis";

// Tag-based invalidation: associate cache keys with tags
export async function cacheWithTags<T>(
  key: string,
  tags: string[],
  fetcher: () => Promise<T>,
  ttl: number
): Promise<T> {
  const data = await fetcher();

  const pipeline = redis.pipeline();
  pipeline.setex(key, ttl, JSON.stringify(data));
  for (const tag of tags) {
    pipeline.sadd(`tag:${tag}`, key);
    pipeline.expire(`tag:${tag}`, ttl + 60);
  }
  await pipeline.exec();

  return data;
}

export async function invalidateByTag(tag: string): Promise<number> {
  const keys = await redis.smembers(`tag:${tag}`);
  if (keys.length === 0) return 0;

  const pipeline = redis.pipeline();
  for (const key of keys) pipeline.del(key);
  pipeline.del(`tag:${tag}`);
  await pipeline.exec();

  return keys.length;
}

// Usage:
// Cache product listing tagged with org and "products"
// await cacheWithTags(`products:${orgId}`, [`org:${orgId}`, "products"], fetcher, 300)
// When a product is updated: await invalidateByTag(`org:${orgId}`)
```

## Step 4: Rate Limiting with Sliding Window

```typescript
// src/middleware/rate-limit.ts
import { redis } from "../lib/redis";
import type { NextRequest } from "next/server";

interface RateLimitConfig {
  windowMs: number;
  maxRequests: number;
}

export async function rateLimit(
  identifier: string,
  config: RateLimitConfig
): Promise<{ allowed: boolean; remaining: number; resetAt: number }> {
  const now = Date.now();
  const windowStart = now - config.windowMs;
  const key = `ratelimit:${identifier}`;

  const pipeline = redis.pipeline();
  pipeline.zremrangebyscore(key, 0, windowStart);  // Remove old entries
  pipeline.zadd(key, now, `${now}-${Math.random()}`);  // Add current request
  pipeline.zcard(key);  // Count requests in window
  pipeline.pexpire(key, config.windowMs);  // Set TTL

  const results = await pipeline.exec();
  const requestCount = results![2][1] as number;
  const allowed = requestCount <= config.maxRequests;

  return {
    allowed,
    remaining: Math.max(0, config.maxRequests - requestCount),
    resetAt: now + config.windowMs,
  };
}

// Middleware usage
export async function rateLimitMiddleware(req: NextRequest) {
  const ip = req.headers.get("x-forwarded-for") || "unknown";
  const { allowed, remaining, resetAt } = await rateLimit(ip, {
    windowMs: 60_000,   // 1 minute window
    maxRequests: 100,    // 100 requests per minute
  });

  if (!allowed) {
    return new Response("Too Many Requests", {
      status: 429,
      headers: {
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": String(Math.ceil(resetAt / 1000)),
        "Retry-After": String(Math.ceil((resetAt - Date.now()) / 1000)),
      },
    });
  }
}
```

## Step 5: Use in API Routes

```typescript
// src/app/api/products/route.ts
import { cached, invalidateByTag } from "@/lib/cache";
import { getProducts, createProduct } from "@/db/queries/products";

export async function GET(req: NextRequest) {
  const orgId = getOrgId(req);

  const products = await cached(
    `products:${orgId}:list`,
    () => getProducts(orgId),
    { ttl: 300, staleWhileRevalidate: 60 }
  );

  return Response.json(products);
}

export async function POST(req: NextRequest) {
  const orgId = getOrgId(req);
  const body = await req.json();

  const product = await createProduct({ ...body, orgId });

  // Invalidate all caches tagged with this org
  await invalidateByTag(`org:${orgId}`);

  return Response.json(product, { status: 201 });
}
```

## Summary

Raj's database load dropped 90%. The cache-aside pattern with stale-while-revalidate means users always get fast responses — even when the cache expires, they get the stale version while a background refresh happens. Tag-based invalidation ensures that when a product is updated, all related caches (listings, search results, org dashboards) are cleared correctly. The sliding window rate limiter handles abuse without blocking legitimate users, and it's all running on a single Redis instance that uses 200MB of RAM.
