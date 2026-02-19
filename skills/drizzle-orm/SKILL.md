---
name: drizzle-orm
description: >-
  Build type-safe database layers with Drizzle ORM — schema definition in
  TypeScript, SQL-like query builder, migrations, relations, and prepared
  statements. Use when tasks need a lightweight, SQL-first ORM for TypeScript
  with zero code generation, edge runtime support, or migration from raw SQL.
license: Apache-2.0
compatibility: "Requires Node.js 16+"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: development
  tags: ["drizzle", "orm", "database", "typescript", "sql"]
---

# Drizzle ORM

Lightweight, SQL-first TypeScript ORM. No code generation step -- schema is TypeScript, queries look like SQL, and it runs everywhere (Node.js, Bun, Deno, Cloudflare Workers, Vercel Edge).

## Setup

```bash
# PostgreSQL
npm install drizzle-orm postgres
npm install drizzle-kit --save-dev

# MySQL
npm install drizzle-orm mysql2

# SQLite (for Bun/local dev)
npm install drizzle-orm better-sqlite3
```

## Schema Definition

Unlike Prisma's custom DSL, Drizzle schemas are plain TypeScript files:

```typescript
// src/db/schema.ts — Application schema in TypeScript

import {
  pgTable, text, varchar, integer, boolean, timestamp,
  serial, pgEnum, uniqueIndex, index, primaryKey,
} from 'drizzle-orm/pg-core';
import { relations } from 'drizzle-orm';

// Enums
export const roleEnum = pgEnum('role', ['admin', 'member', 'viewer']);
export const planEnum = pgEnum('plan', ['free', 'pro', 'enterprise']);
export const taskStatusEnum = pgEnum('task_status', ['todo', 'in_progress', 'in_review', 'done']);

// Tables
export const organizations = pgTable('organizations', {
  id: text('id').primaryKey().$defaultFn(() => crypto.randomUUID()),
  name: varchar('name', { length: 255 }).notNull(),
  slug: varchar('slug', { length: 100 }).notNull().unique(),
  plan: planEnum('plan').default('free').notNull(),
  createdAt: timestamp('created_at').defaultNow().notNull(),
}, (table) => ({
  slugIdx: uniqueIndex('org_slug_idx').on(table.slug),
}));

export const users = pgTable('users', {
  id: text('id').primaryKey().$defaultFn(() => crypto.randomUUID()),
  email: varchar('email', { length: 255 }).notNull().unique(),
  name: varchar('name', { length: 255 }),
  role: roleEnum('role').default('member').notNull(),
  organizationId: text('organization_id').notNull()
    .references(() => organizations.id),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
}, (table) => ({
  emailIdx: uniqueIndex('user_email_idx').on(table.email),
  orgIdx: index('user_org_idx').on(table.organizationId),
}));

export const projects = pgTable('projects', {
  id: text('id').primaryKey().$defaultFn(() => crypto.randomUUID()),
  name: varchar('name', { length: 255 }).notNull(),
  description: text('description'),
  organizationId: text('organization_id').notNull()
    .references(() => organizations.id, { onDelete: 'cascade' }),
  createdAt: timestamp('created_at').defaultNow().notNull(),
}, (table) => ({
  orgNameIdx: uniqueIndex('project_org_name_idx').on(table.organizationId, table.name),
}));

export const tasks = pgTable('tasks', {
  id: text('id').primaryKey().$defaultFn(() => crypto.randomUUID()),
  title: varchar('title', { length: 500 }).notNull(),
  status: taskStatusEnum('status').default('todo').notNull(),
  priority: integer('priority').default(0).notNull(),  // 0=low, 1=med, 2=high, 3=urgent
  projectId: text('project_id').notNull()
    .references(() => projects.id, { onDelete: 'cascade' }),
  assigneeId: text('assignee_id').references(() => users.id),
  dueDate: timestamp('due_date'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
}, (table) => ({
  projectStatusIdx: index('task_project_status_idx').on(table.projectId, table.status),
  assigneeIdx: index('task_assignee_idx').on(table.assigneeId),
}));

// Relations (for the relational query API)
export const organizationsRelations = relations(organizations, ({ many }) => ({
  users: many(users),
  projects: many(projects),
}));

export const usersRelations = relations(users, ({ one, many }) => ({
  organization: one(organizations, {
    fields: [users.organizationId],
    references: [organizations.id],
  }),
  assignedTasks: many(tasks),
}));

export const projectsRelations = relations(projects, ({ one, many }) => ({
  organization: one(organizations, {
    fields: [projects.organizationId],
    references: [organizations.id],
  }),
  tasks: many(tasks),
}));

export const tasksRelations = relations(tasks, ({ one }) => ({
  project: one(projects, {
    fields: [tasks.projectId],
    references: [projects.id],
  }),
  assignee: one(users, {
    fields: [tasks.assigneeId],
    references: [users.id],
  }),
}));
```

## Database Connection

```typescript
// src/db/index.ts — Database connection

import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import * as schema from './schema';

const connection = postgres(process.env.DATABASE_URL!, {
  max: 20,  // Connection pool size
});

export const db = drizzle(connection, { schema });
```

## Queries

### SQL-Like Query Builder

Drizzle queries read like SQL -- if you know SQL, you know Drizzle:

```typescript
// queries.ts — SQL-like queries with full type safety

import { db } from './db';
import { users, tasks, projects, organizations } from './db/schema';
import { eq, and, or, gt, lt, like, ilike, inArray, desc, asc, count, sql } from 'drizzle-orm';

/** Find users by organization with optional search. */
async function listUsers(orgId: string, search?: string) {
  return db.select()
    .from(users)
    .where(
      search
        ? and(
            eq(users.organizationId, orgId),
            or(
              ilike(users.name, `%${search}%`),
              ilike(users.email, `%${search}%`),
            ),
          )
        : eq(users.organizationId, orgId)
    )
    .orderBy(desc(users.createdAt))
    .limit(20);
}

/** Join tasks with project and assignee info. */
async function getProjectTasks(projectId: string) {
  return db.select({
    taskId: tasks.id,
    title: tasks.title,
    status: tasks.status,
    priority: tasks.priority,
    dueDate: tasks.dueDate,
    assigneeName: users.name,
    assigneeEmail: users.email,
  })
  .from(tasks)
  .leftJoin(users, eq(tasks.assigneeId, users.id))
  .where(eq(tasks.projectId, projectId))
  .orderBy(desc(tasks.priority), asc(tasks.createdAt));
}

/** Aggregate: task counts per status for a project. */
async function getTaskStats(projectId: string) {
  return db.select({
    status: tasks.status,
    count: count(),
  })
  .from(tasks)
  .where(eq(tasks.projectId, projectId))
  .groupBy(tasks.status);
}
```

### Relational Query API

For nested data (like Prisma's `include`):

```typescript
/** Fetch organization with all nested relations. */
async function getOrgDashboard(slug: string) {
  return db.query.organizations.findFirst({
    where: eq(organizations.slug, slug),
    with: {
      users: {
        orderBy: [desc(users.createdAt)],
        limit: 10,
      },
      projects: {
        with: {
          tasks: {
            where: or(
              eq(tasks.status, 'todo'),
              eq(tasks.status, 'in_progress'),
            ),
            orderBy: [desc(tasks.priority)],
          },
        },
      },
    },
  });
}
```

### Insert, Update, Delete

```typescript
/** Create a user and return the created record. */
async function createUser(data: { email: string; name: string; orgId: string }) {
  const [user] = await db.insert(users).values({
    email: data.email,
    name: data.name,
    organizationId: data.orgId,
  }).returning();  // PostgreSQL returning clause
  return user;
}

/** Bulk insert tasks. */
async function createTasks(projectId: string, taskList: Array<{ title: string; priority: number }>) {
  return db.insert(tasks).values(
    taskList.map(t => ({ title: t.title, priority: t.priority, projectId }))
  ).returning();
}

/** Update with conditions. */
async function completeOverdueTasks(projectId: string) {
  return db.update(tasks)
    .set({ status: 'done', updatedAt: new Date() })
    .where(and(
      eq(tasks.projectId, projectId),
      lt(tasks.dueDate, new Date()),
      eq(tasks.status, 'todo'),
    ))
    .returning();
}

/** Delete with cascade. */
async function deleteProject(projectId: string) {
  return db.delete(projects).where(eq(projects.id, projectId));
  // Tasks deleted automatically via onDelete: 'cascade'
}

/** Upsert (insert or update on conflict). */
async function upsertUser(email: string, name: string, orgId: string) {
  return db.insert(users)
    .values({ email, name, organizationId: orgId })
    .onConflictDoUpdate({
      target: users.email,
      set: { name, updatedAt: new Date() },
    })
    .returning();
}
```

### Transactions

```typescript
/** Transfer a task between projects atomically. */
async function transferTask(taskId: string, toProjectId: string) {
  return db.transaction(async (tx) => {
    const [task] = await tx.select().from(tasks).where(eq(tasks.id, taskId));
    if (!task) throw new Error('Task not found');

    // Verify target project exists and is in same org
    const [targetProject] = await tx.select().from(projects)
      .where(eq(projects.id, toProjectId));
    if (!targetProject) throw new Error('Target project not found');

    return tx.update(tasks)
      .set({ projectId: toProjectId, updatedAt: new Date() })
      .where(eq(tasks.id, taskId))
      .returning();
  });
}
```

### Prepared Statements

For frequently executed queries (skips query building overhead):

```typescript
const findUserByEmail = db.select()
  .from(users)
  .where(eq(users.email, sql.placeholder('email')))
  .prepare('find_user_by_email');

// Execute — fast, reuses the prepared statement
const user = await findUserByEmail.execute({ email: 'dev@example.com' });
```

## Migrations

```typescript
// drizzle.config.ts
import type { Config } from 'drizzle-kit';

export default {
  schema: './src/db/schema.ts',
  out: './drizzle',
  dialect: 'postgresql',
  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },
} satisfies Config;
```

```bash
# Generate migration from schema changes
npx drizzle-kit generate

# Apply migrations
npx drizzle-kit migrate

# Push schema directly (dev only — no migration files)
npx drizzle-kit push

# Visual schema browser
npx drizzle-kit studio
```

## Drizzle vs Prisma

| | Drizzle | Prisma |
|---|---|---|
| Schema format | TypeScript files | Custom `.prisma` DSL |
| Code generation | None needed | Required (`prisma generate`) |
| Query style | SQL-like builder | Method chaining |
| Bundle size | ~50KB | ~1.8MB |
| Edge runtime | Yes (Workers, Vercel Edge) | Limited |
| Raw SQL | First-class citizen | Escape hatch |
| Learning curve | Know SQL = know Drizzle | New API to learn |

## Guidelines

- Define relations explicitly even though foreign keys exist -- Drizzle needs them for the relational query API
- Use `.returning()` on inserts/updates in PostgreSQL to get the result without a separate query
- Prefer the SQL-like API (`db.select()`) for simple queries and the relational API (`db.query`) for nested data
- Always define indexes in the schema for columns used in `where` and `orderBy`
- Use `sql.placeholder()` with `.prepare()` for hot-path queries
- Run `drizzle-kit generate` after every schema change -- don't edit migration files manually
- Use `drizzle-kit push` only in development -- production needs versioned migration files
- Connection pool size should match your server's concurrency (default 10 is often too low)
