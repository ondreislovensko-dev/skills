---
title: Build a Type-Safe Database Layer with Drizzle ORM
slug: build-type-safe-database-layer-with-drizzle
description: >-
  Design a production database layer using Drizzle ORM with type-safe queries,
  migrations, relational queries, connection pooling, and Drizzle Studio for
  visual database management.
skills:
  - drizzle-orm
  - drizzle-studio
  - neon
  - redis
  - zod
category: development
tags:
  - database
  - orm
  - typescript
  - type-safety
  - migrations
---

# Build a Type-Safe Database Layer with Drizzle ORM

Lena is building a multi-tenant project management app. She's tired of Prisma's heavy client generation and runtime overhead. She wants an ORM that feels like writing SQL but gives her full TypeScript inference — no codegen step, instant schema changes reflected in types, and raw SQL escape hatches when she needs them. She picks Drizzle ORM with Neon's serverless Postgres.

## Step 1: Define the Schema

```typescript
// src/db/schema.ts
import { pgTable, text, timestamp, integer, boolean, uuid, index, uniqueIndex } from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";

export const organizations = pgTable("organizations", {
  id: uuid("id").defaultRandom().primaryKey(),
  name: text("name").notNull(),
  slug: text("slug").notNull(),
  plan: text("plan", { enum: ["free", "pro", "enterprise"] }).default("free").notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
}, (t) => [
  uniqueIndex("org_slug_idx").on(t.slug),
]);

export const users = pgTable("users", {
  id: uuid("id").defaultRandom().primaryKey(),
  email: text("email").notNull(),
  name: text("name").notNull(),
  orgId: uuid("org_id").references(() => organizations.id, { onDelete: "cascade" }).notNull(),
  role: text("role", { enum: ["owner", "admin", "member"] }).default("member").notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
}, (t) => [
  uniqueIndex("user_email_idx").on(t.email),
  index("user_org_idx").on(t.orgId),
]);

export const projects = pgTable("projects", {
  id: uuid("id").defaultRandom().primaryKey(),
  name: text("name").notNull(),
  description: text("description"),
  orgId: uuid("org_id").references(() => organizations.id, { onDelete: "cascade" }).notNull(),
  ownerId: uuid("owner_id").references(() => users.id).notNull(),
  isArchived: boolean("is_archived").default(false).notNull(),
  taskCount: integer("task_count").default(0).notNull(),
  createdAt: timestamp("created_at").defaultNow().notNull(),
}, (t) => [
  index("project_org_idx").on(t.orgId),
]);

// Relations for relational queries
export const organizationsRelations = relations(organizations, ({ many }) => ({
  users: many(users),
  projects: many(projects),
}));

export const usersRelations = relations(users, ({ one, many }) => ({
  organization: one(organizations, { fields: [users.orgId], references: [organizations.id] }),
  ownedProjects: many(projects),
}));

export const projectsRelations = relations(projects, ({ one }) => ({
  organization: one(organizations, { fields: [projects.orgId], references: [organizations.id] }),
  owner: one(users, { fields: [projects.ownerId], references: [users.id] }),
}));
```

## Step 2: Configure Drizzle with Neon

```typescript
// src/db/index.ts
import { drizzle } from "drizzle-orm/neon-http";
import { neon } from "@neondatabase/serverless";
import * as schema from "./schema";

const sql = neon(process.env.DATABASE_URL!);
export const db = drizzle(sql, { schema });
export type Database = typeof db;
```

```typescript
// drizzle.config.ts
import { defineConfig } from "drizzle-kit";

export default defineConfig({
  schema: "./src/db/schema.ts",
  out: "./drizzle",
  dialect: "postgresql",
  dbCredentials: { url: process.env.DATABASE_URL! },
});
```

```bash
# Generate and apply migrations
npx drizzle-kit generate
npx drizzle-kit migrate

# Open Drizzle Studio for visual DB management
npx drizzle-kit studio
```

## Step 3: Build Type-Safe Query Functions

```typescript
// src/db/queries/projects.ts
import { eq, and, desc, sql, ilike } from "drizzle-orm";
import { db } from "..";
import { projects, users } from "../schema";

export async function getProjectsForOrg(orgId: string, search?: string) {
  return db.query.projects.findMany({
    where: and(
      eq(projects.orgId, orgId),
      eq(projects.isArchived, false),
      search ? ilike(projects.name, `%${search}%`) : undefined
    ),
    with: {
      owner: { columns: { id: true, name: true, email: true } },
    },
    orderBy: [desc(projects.createdAt)],
    limit: 50,
  });
  // Return type is fully inferred — no manual typing needed
}

export async function createProject(data: {
  name: string;
  description?: string;
  orgId: string;
  ownerId: string;
}) {
  const [project] = await db.insert(projects).values(data).returning();
  return project; // Type: typeof projects.$inferSelect
}

export async function getOrgStats(orgId: string) {
  const [stats] = await db
    .select({
      totalProjects: sql<number>`count(*)::int`,
      activeProjects: sql<number>`count(*) filter (where not ${projects.isArchived})::int`,
      totalTasks: sql<number>`coalesce(sum(${projects.taskCount}), 0)::int`,
    })
    .from(projects)
    .where(eq(projects.orgId, orgId));

  return stats;
}
```

## Step 4: Add a Caching Layer

```typescript
// src/db/cached.ts
import { Redis } from "ioredis";
import { getProjectsForOrg, getOrgStats } from "./queries/projects";

const redis = new Redis(process.env.REDIS_URL!);

export async function getCachedProjects(orgId: string, search?: string) {
  if (search) return getProjectsForOrg(orgId, search); // Don't cache searches

  const cacheKey = `projects:${orgId}`;
  const cached = await redis.get(cacheKey);
  if (cached) return JSON.parse(cached);

  const projects = await getProjectsForOrg(orgId);
  await redis.setex(cacheKey, 300, JSON.stringify(projects)); // 5 min TTL
  return projects;
}

export function invalidateProjectCache(orgId: string) {
  return redis.del(`projects:${orgId}`);
}
```

## Step 5: Transactions for Complex Operations

```typescript
// src/db/queries/organizations.ts
import { db } from "..";
import { organizations, users, projects } from "../schema";

export async function createOrgWithOwner(input: {
  orgName: string;
  orgSlug: string;
  ownerEmail: string;
  ownerName: string;
}) {
  return db.transaction(async (tx) => {
    const [org] = await tx.insert(organizations).values({
      name: input.orgName,
      slug: input.orgSlug,
    }).returning();

    const [owner] = await tx.insert(users).values({
      email: input.ownerEmail,
      name: input.ownerName,
      orgId: org.id,
      role: "owner",
    }).returning();

    const [defaultProject] = await tx.insert(projects).values({
      name: "My First Project",
      orgId: org.id,
      ownerId: owner.id,
    }).returning();

    return { org, owner, defaultProject };
  });
}
```

## Summary

Lena has a fully type-safe database layer where every query result is automatically typed — no codegen, no manual type definitions. Drizzle's relational queries give her Prisma-like `with` syntax for joins, while raw SQL escape hatches handle complex aggregations. Drizzle Studio lets her browse and edit data visually during development. Migrations are SQL files she can review and version control. The Redis caching layer keeps reads fast, and transactions ensure data consistency for multi-table operations.
