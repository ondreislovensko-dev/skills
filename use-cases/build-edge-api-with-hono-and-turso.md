---
title: Build an Edge API with Hono and Turso
slug: build-edge-api-with-hono-and-turso
description: >-
  Build a globally distributed API using Hono framework on Cloudflare Workers
  with Turso's embedded SQLite replicas for sub-10ms database reads from
  any region — authentication, CRUD, and edge caching included.
skills:
  - turso
  - drizzle-orm
  - zod
  - docker-compose
category: development
tags:
  - edge
  - serverless
  - hono
  - turso
  - sqlite
  - api
---

# Build an Edge API with Hono and Turso

Priya's API serves users across 6 continents but her database is in us-east-1. Users in Asia and Europe experience 200-300ms latency just from the database round-trip. She wants to run her API at the edge (Cloudflare Workers in 300+ locations) with database reads that feel local. Turso's embedded replicas sync SQLite to each edge location, giving her sub-10ms reads everywhere while writes go to the primary.

## Step 1: Project Setup

```bash
npm create hono@latest my-edge-api -- --template cloudflare-workers
cd my-edge-api
npm install @libsql/client drizzle-orm zod hono
npm install -D drizzle-kit @cloudflare/workers-types
```

```toml
# wrangler.toml
name = "my-edge-api"
main = "src/index.ts"
compatibility_date = "2024-12-01"

[vars]
TURSO_DATABASE_URL = "libsql://mydb-myorg.turso.io"

# Secrets (set via wrangler secret put)
# TURSO_AUTH_TOKEN
# JWT_SECRET
```

## Step 2: Database Schema with Drizzle

```typescript
// src/db/schema.ts
import { sqliteTable, text, integer } from "drizzle-orm/sqlite-core";

export const users = sqliteTable("users", {
  id: text("id").primaryKey(),
  email: text("email").notNull().unique(),
  name: text("name").notNull(),
  passwordHash: text("password_hash").notNull(),
  plan: text("plan", { enum: ["free", "pro", "enterprise"] }).default("free").notNull(),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull().$defaultFn(() => new Date()),
});

export const posts = sqliteTable("posts", {
  id: text("id").primaryKey(),
  title: text("title").notNull(),
  content: text("content").notNull(),
  slug: text("slug").notNull().unique(),
  authorId: text("author_id").references(() => users.id).notNull(),
  status: text("status", { enum: ["draft", "published", "archived"] }).default("draft").notNull(),
  publishedAt: integer("published_at", { mode: "timestamp" }),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull().$defaultFn(() => new Date()),
});

export const apiKeys = sqliteTable("api_keys", {
  id: text("id").primaryKey(),
  userId: text("user_id").references(() => users.id).notNull(),
  keyHash: text("key_hash").notNull(),
  name: text("name").notNull(),
  lastUsedAt: integer("last_used_at", { mode: "timestamp" }),
  expiresAt: integer("expires_at", { mode: "timestamp" }),
});
```

## Step 3: Hono API with Edge Database

```typescript
// src/index.ts
import { Hono } from "hono";
import { cors } from "hono/cors";
import { zValidator } from "@hono/zod-validator";
import { createClient } from "@libsql/client/web";
import { drizzle } from "drizzle-orm/libsql";
import { eq } from "drizzle-orm";
import { z } from "zod";
import * as schema from "./db/schema";

type Bindings = {
  TURSO_DATABASE_URL: string;
  TURSO_AUTH_TOKEN: string;
  JWT_SECRET: string;
};

const app = new Hono<{ Bindings: Bindings }>();

// Middleware: create DB connection per request (edge-compatible)
app.use("*", async (c, next) => {
  const client = createClient({
    url: c.env.TURSO_DATABASE_URL,
    authToken: c.env.TURSO_AUTH_TOKEN,
  });
  c.set("db", drizzle(client, { schema }));
  await next();
});

app.use("*", cors());

// List published posts — reads from nearest replica
app.get(
  "/api/posts",
  zValidator("query", z.object({
    limit: z.coerce.number().min(1).max(100).default(20),
    offset: z.coerce.number().min(0).default(0),
  })),
  async (c) => {
    const { limit, offset } = c.req.valid("query");
    const db = c.get("db");

    const posts = await db.query.posts.findMany({
      where: eq(schema.posts.status, "published"),
      with: { author: { columns: { id: true, name: true } } },
      orderBy: (t, { desc }) => [desc(t.publishedAt)],
      limit,
      offset,
    });

    return c.json({ posts, limit, offset });
  }
);

// Get single post by slug
app.get("/api/posts/:slug", async (c) => {
  const db = c.get("db");
  const post = await db.query.posts.findFirst({
    where: eq(schema.posts.slug, c.req.param("slug")),
    with: { author: { columns: { id: true, name: true } } },
  });

  if (!post) return c.json({ error: "Not found" }, 404);
  return c.json(post);
});

// Create post — writes go to primary
app.post(
  "/api/posts",
  authMiddleware,
  zValidator("json", z.object({
    title: z.string().min(1).max(200),
    content: z.string().min(1),
    slug: z.string().regex(/^[a-z0-9-]+$/).min(3).max(100),
    status: z.enum(["draft", "published"]).default("draft"),
  })),
  async (c) => {
    const db = c.get("db");
    const body = c.req.valid("json");
    const userId = c.get("userId");

    const [post] = await db.insert(schema.posts).values({
      id: crypto.randomUUID(),
      ...body,
      authorId: userId,
      publishedAt: body.status === "published" ? new Date() : null,
    }).returning();

    return c.json(post, 201);
  }
);

// Health check with region info
app.get("/health", (c) => {
  return c.json({
    status: "ok",
    region: c.req.header("cf-ray")?.split("-").pop() || "unknown",
    timestamp: new Date().toISOString(),
  });
});

export default app;
```

## Step 4: Authentication Middleware

```typescript
// src/middleware/auth.ts
import { createMiddleware } from "hono/factory";

export const authMiddleware = createMiddleware(async (c, next) => {
  const authHeader = c.req.header("Authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    return c.json({ error: "Missing token" }, 401);
  }

  const token = authHeader.slice(7);

  try {
    // Verify JWT using Web Crypto API (edge-compatible)
    const payload = await verifyJWT(token, c.env.JWT_SECRET);
    c.set("userId", payload.sub);
    await next();
  } catch {
    return c.json({ error: "Invalid token" }, 401);
  }
});

async function verifyJWT(token: string, secret: string): Promise<{ sub: string }> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"]
  );

  const [headerB64, payloadB64, signatureB64] = token.split(".");
  const data = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
  const signature = Uint8Array.from(atob(signatureB64.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));

  const valid = await crypto.subtle.verify("HMAC", key, signature, data);
  if (!valid) throw new Error("Invalid signature");

  const payload = JSON.parse(atob(payloadB64));
  if (payload.exp && payload.exp < Date.now() / 1000) throw new Error("Expired");

  return payload;
}
```

## Step 5: Deploy

```bash
# Set secrets
wrangler secret put TURSO_AUTH_TOKEN
wrangler secret put JWT_SECRET

# Push schema to Turso
npx drizzle-kit push

# Deploy to Cloudflare Workers
wrangler deploy

# Test from different regions
curl https://my-edge-api.workers.dev/health
# {"status":"ok","region":"SIN","timestamp":"..."}
```

## Summary

Priya's API now runs in 300+ Cloudflare edge locations. Read queries hit Turso's local SQLite replica — sub-10ms from Singapore, São Paulo, or Stockholm. Writes route to the primary database and replicate automatically. Hono gives her Express-like ergonomics in an edge-compatible package with Zod validation, middleware, and type safety. The entire API runs on Cloudflare's free tier for small workloads, and scales to millions of requests without managing servers. Cold starts are under 5ms because it's not a container — it's V8 isolates.
