---
title: Build Type-Safe Error Handling with Effect-TS
slug: build-type-safe-error-handling-with-effect-ts
description: >-
  Replace try/catch with Effect-TS for type-safe error handling — track all
  possible errors in the type system, compose operations safely, handle
  retries and timeouts declaratively, and never miss an error case.
skills:
  - effect-ts
  - drizzle-orm
  - zod
category: development
tags:
  - error-handling
  - effect-ts
  - typescript
  - type-safety
  - functional
---

# Build Type-Safe Error Handling with Effect-TS

Wren's API has `try/catch` everywhere but errors are invisible in types. A function returns `Promise<User>` but can actually throw 5 different errors — database connection failure, not found, validation error, permission denied, timeout. Callers don't know what to handle. Effect-TS makes every possible error part of the type signature: `Effect<User, NotFoundError | DbError | ValidationError>`. The compiler forces you to handle them all.

## Step 1: Define Typed Errors

```typescript
// src/errors.ts
import { Data } from "effect";

// Each error is a tagged class — discriminated union friendly
export class NotFoundError extends Data.TaggedError("NotFoundError")<{
  resource: string;
  id: string;
}> {}

export class ValidationError extends Data.TaggedError("ValidationError")<{
  field: string;
  message: string;
}> {}

export class DatabaseError extends Data.TaggedError("DatabaseError")<{
  operation: string;
  cause: unknown;
}> {}

export class PermissionError extends Data.TaggedError("PermissionError")<{
  userId: string;
  action: string;
  resource: string;
}> {}

export class ExternalApiError extends Data.TaggedError("ExternalApiError")<{
  service: string;
  statusCode: number;
  message: string;
}> {}
```

## Step 2: Wrap Database Operations

```typescript
// src/services/user-service.ts
import { Effect, pipe } from "effect";
import { NotFoundError, DatabaseError, ValidationError } from "../errors";
import { db } from "../db";
import { users } from "../db/schema";
import { eq } from "drizzle-orm";

// Return type: Effect<User, NotFoundError | DatabaseError>
// The type signature tells callers EXACTLY what can go wrong
export const getUser = (id: string) =>
  Effect.tryPromise({
    try: () => db.query.users.findFirst({ where: eq(users.id, id) }),
    catch: (error) => new DatabaseError({ operation: "getUser", cause: error }),
  }).pipe(
    Effect.flatMap((user) =>
      user
        ? Effect.succeed(user)
        : Effect.fail(new NotFoundError({ resource: "User", id }))
    )
  );

// Return type: Effect<User, ValidationError | DatabaseError>
export const createUser = (input: { email: string; name: string }) =>
  pipe(
    // Validate
    Effect.if(input.email.includes("@"), {
      onTrue: () => Effect.succeed(input),
      onFalse: () => Effect.fail(new ValidationError({ field: "email", message: "Invalid email" })),
    }),
    // Insert
    Effect.flatMap((validated) =>
      Effect.tryPromise({
        try: () =>
          db.insert(users).values({
            id: crypto.randomUUID(),
            email: validated.email,
            name: validated.name,
            createdAt: new Date(),
          }).returning().then((rows) => rows[0]),
        catch: (error) => new DatabaseError({ operation: "createUser", cause: error }),
      })
    )
  );
```

## Step 3: Compose Effects Safely

```typescript
// src/services/project-service.ts
import { Effect, pipe } from "effect";
import { getUser } from "./user-service";
import { PermissionError, NotFoundError, DatabaseError } from "../errors";

// Type: Effect<Project, NotFoundError | DatabaseError | PermissionError>
// Errors from getUser automatically propagate into this function's type
export const getProjectWithOwner = (projectId: string, requesterId: string) =>
  pipe(
    // Get project (can fail with NotFoundError | DatabaseError)
    getProject(projectId),
    // Check permission (adds PermissionError to possible failures)
    Effect.flatMap((project) =>
      project.ownerId === requesterId || project.memberIds.includes(requesterId)
        ? Effect.succeed(project)
        : Effect.fail(new PermissionError({
            userId: requesterId,
            action: "read",
            resource: `project:${projectId}`,
          }))
    ),
    // Enrich with owner data (adds owner's errors to the type)
    Effect.flatMap((project) =>
      Effect.map(getUser(project.ownerId), (owner) => ({
        ...project,
        owner,
      }))
    )
  );
```

## Step 4: Handle Errors at the API Boundary

```typescript
// src/app/api/projects/[id]/route.ts
import { Effect, Match, pipe } from "effect";
import { getProjectWithOwner } from "@/services/project-service";
import { NotFoundError, DatabaseError, PermissionError } from "@/errors";

export async function GET(req: Request, { params }: { params: { id: string } }) {
  const userId = await getAuthenticatedUserId(req);

  const result = await pipe(
    getProjectWithOwner(params.id, userId),
    // Handle each error type explicitly — compiler ensures exhaustive handling
    Effect.catchTags({
      NotFoundError: (err) =>
        Effect.succeed(Response.json({ error: `${err.resource} not found` }, { status: 404 })),
      DatabaseError: (err) => {
        console.error("DB error:", err.cause);
        return Effect.succeed(Response.json({ error: "Internal server error" }, { status: 500 }));
      },
      PermissionError: (err) =>
        Effect.succeed(Response.json({ error: "Access denied" }, { status: 403 })),
    }),
    // Success case
    Effect.map((project) => Response.json(project)),
    Effect.runPromise
  );

  return result;
}
```

## Step 5: Retry and Timeout Policies

```typescript
// src/services/external-api.ts
import { Effect, Schedule, Duration, pipe } from "effect";
import { ExternalApiError } from "../errors";

const fetchEnrichmentData = (userId: string) =>
  Effect.tryPromise({
    try: async () => {
      const res = await fetch(`https://api.enrichment.com/users/${userId}`);
      if (!res.ok) throw { status: res.status, body: await res.text() };
      return res.json();
    },
    catch: (error: any) =>
      new ExternalApiError({
        service: "enrichment",
        statusCode: error.status || 500,
        message: error.body || "Unknown error",
      }),
  });

// Retry 3 times with exponential backoff, timeout after 5 seconds
export const getEnrichmentData = (userId: string) =>
  pipe(
    fetchEnrichmentData(userId),
    Effect.retry(
      Schedule.exponential(Duration.millis(200)).pipe(
        Schedule.compose(Schedule.recurs(3))
      )
    ),
    Effect.timeout(Duration.seconds(5)),
    // If enrichment fails, return empty data instead of failing the whole request
    Effect.catchAll(() => Effect.succeed({ enriched: false }))
  );
```

## Summary

Wren's API now has zero unhandled errors. Every function's type signature declares exactly what can fail — `getProjectWithOwner` returns `Effect<ProjectWithOwner, NotFoundError | DatabaseError | PermissionError>`, and the compiler won't let you ignore any case. Adding a new error type to a service function causes compile errors in every caller that doesn't handle it. Retry policies for external APIs are declarative, not imperative. The `catchTags` pattern replaces messy instanceof chains with exhaustive pattern matching. The team catches error-handling bugs at compile time instead of in production.
