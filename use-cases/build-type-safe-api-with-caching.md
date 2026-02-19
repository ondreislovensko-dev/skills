---
title: Build a Type-Safe API with Redis Caching
slug: build-type-safe-api-with-caching
description: "Set up a production-ready TypeScript API with Prisma for type-safe database access and Redis for caching, session management, and rate limiting."
skills: [prisma, redis]
category: development
tags: [prisma, redis, typescript, api, caching, performance]
---

# Build a Type-Safe API with Redis Caching

## The Problem

A growing SaaS application serves 2,000 daily active users across a REST API. The API reads from PostgreSQL for every request -- user profiles, team settings, permission checks, and feature flags. Response times average 180ms but spike to 800ms during peak hours when the database connection pool saturates. The most expensive queries run repeatedly: the same user profile loads on every authenticated request, team settings load on every permission check, and feature flags load on every page render.

The team tried adding query-level caching with a simple in-memory Map, but it doesn't work across multiple API server instances behind a load balancer. Each instance maintains its own cache, so invalidation is inconsistent -- one server serves stale data while another has the fresh version. They need a shared cache that all instances read from, with proper invalidation when data changes.

## The Solution

Use **prisma** for type-safe database access and **redis** for a shared caching layer, session storage, and rate limiting. The architecture is straightforward: Prisma handles all database operations with full TypeScript types, Redis sits in front as a cache-aside layer for hot data, and a thin wrapper ensures cache invalidation happens automatically whenever Prisma writes to the database.

```bash
npm install @prisma/client ioredis express
npm install prisma typescript @types/express --save-dev
npx prisma init
```

## Step-by-Step Walkthrough

### Step 1: Define the Data Model

The Prisma schema defines the full data model. Types generated from this schema flow through every layer of the application, from database queries to API responses to cache serialization:

```text
Set up a Prisma schema for a multi-tenant SaaS app with users, organizations, 
memberships (with roles), and feature flags. Include proper indexes for the 
queries we'll cache: user by ID, user by email, org members list, and feature 
flags by org.
```

```prisma
// prisma/schema.prisma

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        String   @id @default(cuid())
  email     String   @unique
  name      String
  avatarUrl String?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  memberships Membership[]
  sessions    Session[]

  @@index([email])
}

model Organization {
  id        String   @id @default(cuid())
  name      String
  slug      String   @unique
  plan      Plan     @default(FREE)
  createdAt DateTime @default(now())

  memberships  Membership[]
  featureFlags FeatureFlag[]

  @@index([slug])
}

model Membership {
  id             String       @id @default(cuid())
  userId         String
  organizationId String
  role           MemberRole   @default(MEMBER)
  user           User         @relation(fields: [userId], references: [id], onDelete: Cascade)
  organization   Organization @relation(fields: [organizationId], references: [id], onDelete: Cascade)
  createdAt      DateTime     @default(now())

  @@unique([userId, organizationId])
  @@index([organizationId])
}

model FeatureFlag {
  id             String       @id @default(cuid())
  key            String
  enabled        Boolean      @default(false)
  organizationId String
  organization   Organization @relation(fields: [organizationId], references: [id], onDelete: Cascade)

  @@unique([organizationId, key])
  @@index([organizationId])
}

model Session {
  id        String   @id @default(cuid())
  token     String   @unique
  userId    String
  user      User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  expiresAt DateTime
  createdAt DateTime @default(now())

  @@index([token])
  @@index([userId])
}

enum Plan {
  FREE
  PRO
  ENTERPRISE
}

enum MemberRole {
  OWNER
  ADMIN
  MEMBER
  VIEWER
}
```

```bash
npx prisma migrate dev --name init
```

### Step 2: Build the Cache Layer

The cache layer wraps Redis with type-safe get/set operations and automatic serialization. Every cached value includes a TTL and a version prefix so cache entries can be invalidated in bulk when the schema changes:

```typescript
// src/cache.ts — Type-safe Redis cache wrapper

import Redis from 'ioredis';

const redis = new Redis({
  host: process.env.REDIS_HOST || 'localhost',
  port: parseInt(process.env.REDIS_PORT || '6379'),
  password: process.env.REDIS_PASSWORD,
  maxRetriesPerRequest: 3,
});

const CACHE_VERSION = 'v1';  // Bump to invalidate all caches on schema change

/** Build a versioned cache key. */
function key(...parts: string[]): string {
  return `${CACHE_VERSION}:${parts.join(':')}`;
}

/** Get a cached value, parsing JSON automatically. */
export async function cacheGet<T>(cacheKey: string): Promise<T | null> {
  const data = await redis.get(cacheKey);
  if (!data) return null;
  return JSON.parse(data) as T;
}

/** Set a cached value with TTL.
 *
 * @param cacheKey - Redis key.
 * @param value - Data to cache (serialized to JSON).
 * @param ttlSeconds - Time to live. Defaults to 5 minutes.
 */
export async function cacheSet(cacheKey: string, value: unknown, ttlSeconds = 300): Promise<void> {
  await redis.setex(cacheKey, ttlSeconds, JSON.stringify(value));
}

/** Delete one or more cache keys. */
export async function cacheDel(...keys: string[]): Promise<void> {
  if (keys.length > 0) {
    await redis.del(...keys);
  }
}

/** Delete all keys matching a pattern (e.g., invalidate all user caches). */
export async function cacheInvalidatePattern(pattern: string): Promise<void> {
  let cursor = '0';
  do {
    const [nextCursor, keys] = await redis.scan(cursor, 'MATCH', pattern, 'COUNT', 100);
    cursor = nextCursor;
    if (keys.length > 0) {
      await redis.del(...keys);
    }
  } while (cursor !== '0');
}

export { key, redis };
```

### Step 3: Cached Data Access Layer

The data access layer combines Prisma queries with cache-aside logic. Every read checks Redis first; every write invalidates the relevant cache keys. The `withCache` helper reduces boilerplate:

```typescript
// src/data/users.ts — User data access with automatic caching

import { prisma } from '../db';
import { cacheGet, cacheSet, cacheDel, cacheInvalidatePattern, key } from '../cache';
import type { User, Membership, Organization } from '@prisma/client';

type UserWithOrgs = User & {
  memberships: (Membership & { organization: Organization })[];
};

/** Fetch user by ID with organization memberships.
 *  Cache hit: ~1ms. Cache miss: ~15ms (DB) + cache write.
 */
export async function getUserById(userId: string): Promise<UserWithOrgs | null> {
  const cacheKey = key('user', userId);

  // Check cache first
  const cached = await cacheGet<UserWithOrgs>(cacheKey);
  if (cached) return cached;

  // Cache miss — query database
  const user = await prisma.user.findUnique({
    where: { id: userId },
    include: {
      memberships: {
        include: { organization: true },
      },
    },
  });

  if (user) {
    await cacheSet(cacheKey, user, 600);  // Cache for 10 minutes
  }

  return user;
}

/** Fetch user by email (login flow). Shorter TTL since this is auth-critical. */
export async function getUserByEmail(email: string): Promise<User | null> {
  const cacheKey = key('user-email', email);
  const cached = await cacheGet<User>(cacheKey);
  if (cached) return cached;

  const user = await prisma.user.findUnique({ where: { email } });
  if (user) {
    await cacheSet(cacheKey, user, 120);  // 2 minute TTL for auth data
  }
  return user;
}

/** Update user profile and invalidate all related caches. */
export async function updateUser(userId: string, data: { name?: string; avatarUrl?: string }) {
  const user = await prisma.user.update({
    where: { id: userId },
    data,
  });

  // Invalidate both the ID-based and email-based caches
  await cacheDel(key('user', userId), key('user-email', user.email));

  return user;
}

/** Delete user and clean up all cached data. */
export async function deleteUser(userId: string) {
  const user = await prisma.user.delete({ where: { id: userId } });

  // Invalidate user cache + any org member list caches they appeared in
  await cacheDel(key('user', userId), key('user-email', user.email));
  await cacheInvalidatePattern(`${key('org-members')}:*`);

  return user;
}
```

### Step 4: Feature Flags with Redis

Feature flags are the highest-read, lowest-write data in most applications. They load on every request but change maybe once a week. Redis is perfect for this -- the entire flag set for an organization fits in a single key:

```typescript
// src/data/features.ts — Feature flag service with aggressive caching

import { prisma } from '../db';
import { cacheGet, cacheSet, cacheDel, key } from '../cache';

type FlagMap = Record<string, boolean>;

/** Get all feature flags for an organization.
 *  Cached for 30 minutes — flags change rarely.
 */
export async function getFeatureFlags(orgId: string): Promise<FlagMap> {
  const cacheKey = key('flags', orgId);
  const cached = await cacheGet<FlagMap>(cacheKey);
  if (cached) return cached;

  const flags = await prisma.featureFlag.findMany({
    where: { organizationId: orgId },
  });

  const flagMap: FlagMap = {};
  for (const flag of flags) {
    flagMap[flag.key] = flag.enabled;
  }

  await cacheSet(cacheKey, flagMap, 1800);  // 30 minutes
  return flagMap;
}

/** Check a single feature flag. */
export async function isFeatureEnabled(orgId: string, flagKey: string): Promise<boolean> {
  const flags = await getFeatureFlags(orgId);
  return flags[flagKey] ?? false;
}

/** Toggle a feature flag and invalidate cache immediately. */
export async function setFeatureFlag(orgId: string, flagKey: string, enabled: boolean) {
  await prisma.featureFlag.upsert({
    where: { organizationId_key: { organizationId: orgId, key: flagKey } },
    create: { organizationId: orgId, key: flagKey, enabled },
    update: { enabled },
  });

  // Invalidate — next read repopulates from DB
  await cacheDel(key('flags', orgId));
}
```

### Step 5: Rate Limiting Middleware

Rate limiting uses Redis sorted sets for a sliding window algorithm. This protects the API from abuse without adding database load:

```typescript
// src/middleware/rate-limit.ts — Sliding window rate limiter

import { redis } from '../cache';

/** Express middleware for rate limiting.
 *
 * @param limit - Max requests per window.
 * @param windowSeconds - Window size in seconds.
 */
export function rateLimit(limit: number, windowSeconds: number) {
  return async (req: any, res: any, next: any) => {
    // Use authenticated user ID if available, fall back to IP
    const identifier = req.userId || req.ip;
    const redisKey = `ratelimit:${req.path}:${identifier}`;
    const now = Date.now();
    const windowStart = now - windowSeconds * 1000;

    const pipe = redis.pipeline();
    pipe.zremrangebyscore(redisKey, 0, windowStart);  // Remove expired entries
    pipe.zadd(redisKey, now, `${now}-${Math.random()}`);  // Add current request
    pipe.zcard(redisKey);  // Count requests in window
    pipe.expire(redisKey, windowSeconds);  // Auto-cleanup

    const results = await pipe.exec();
    const requestCount = results![2][1] as number;

    // Set rate limit headers so clients can self-throttle
    res.set('X-RateLimit-Limit', String(limit));
    res.set('X-RateLimit-Remaining', String(Math.max(0, limit - requestCount)));
    res.set('X-RateLimit-Reset', String(Math.ceil((now + windowSeconds * 1000) / 1000)));

    if (requestCount > limit) {
      return res.status(429).json({
        error: 'Rate limit exceeded',
        retryAfter: windowSeconds,
      });
    }

    next();
  };
}
```

### Step 6: Wire It Together

```typescript
// src/server.ts — Express API with caching and rate limiting

import express from 'express';
import { getUserById, updateUser } from './data/users';
import { getFeatureFlags, setFeatureFlag } from './data/features';
import { rateLimit } from './middleware/rate-limit';

const app = express();
app.use(express.json());

// Global rate limit: 100 requests per minute per user
app.use(rateLimit(100, 60));

// Strict rate limit on auth endpoints: 10 per minute per IP
app.use('/api/auth/*', rateLimit(10, 60));

app.get('/api/users/:id', async (req, res) => {
  const user = await getUserById(req.params.id);
  if (!user) return res.status(404).json({ error: 'User not found' });
  res.json(user);
});

app.patch('/api/users/:id', async (req, res) => {
  const user = await updateUser(req.params.id, req.body);
  res.json(user);
});

app.get('/api/orgs/:orgId/features', async (req, res) => {
  const flags = await getFeatureFlags(req.params.orgId);
  res.json(flags);
});

app.put('/api/orgs/:orgId/features/:key', async (req, res) => {
  await setFeatureFlag(req.params.orgId, req.params.key, req.body.enabled);
  res.json({ ok: true });
});

app.listen(3000, () => console.log('API running on :3000'));
```

## Real-World Example

A SaaS team deploys the caching layer on a Tuesday morning. Before Redis, their 95th percentile API latency was 340ms during business hours, with the database connection pool regularly hitting 80% capacity across three API server instances. The most-queried endpoint -- `GET /api/users/:id` -- hit the database 12,000 times per hour, running the same query for the same 2,000 users over and over.

After deployment, the user endpoint cache hit rate stabilizes at 94% within the first hour. The 95th percentile drops to 45ms. Database connections drop to 30% utilization because the vast majority of reads never reach PostgreSQL. Feature flag lookups, which previously added 8ms to every request, now add under 1ms with a 99.7% cache hit rate -- they change so rarely that the 30-minute TTL almost never expires before a manual invalidation.

The rate limiter catches an automated scraper on day three -- 400 requests per minute from a single IP hitting the public API. Without the rate limiter, that traffic would have consumed 15% of the database connection pool. With it, the scraper gets 429 responses after its first 100 requests, and the API doesn't even notice.

## Related Skills

- [drizzle-orm](../skills/drizzle-orm/) -- Lighter alternative to Prisma with SQL-first queries
- [supabase](../skills/supabase/) -- Managed PostgreSQL with built-in auth and realtime
