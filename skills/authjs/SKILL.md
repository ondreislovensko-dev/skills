---
name: authjs
description: >-
  Assists with adding authentication to web applications using Auth.js (formerly NextAuth.js).
  Use when configuring OAuth providers, database sessions, JWT strategies, role-based access,
  or multi-tenant auth in Next.js, SvelteKit, Express, or other frameworks. Trigger words:
  authjs, nextauth, oauth, authentication, login, session, providers.
license: Apache-2.0
compatibility: "Requires Node.js 18+"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: development
  tags: ["authjs", "nextauth", "oauth", "authentication", "session"]
---

# Auth.js

## Overview

Auth.js is a universal authentication library for web applications, supporting 80+ OAuth providers, credentials-based login, magic links, and WebAuthn passkeys. It integrates with Next.js, SvelteKit, Express, and other frameworks, offering both JWT and database-backed session strategies with customizable callbacks for role-based access and multi-tenant architectures.

## Instructions

- When setting up authentication, create an `auth.ts` config file with providers, adapter, and callbacks, then wire it into the framework's route handler or middleware.
- When choosing a session strategy, use JWT for stateless apps (marketing sites, public APIs) and database sessions for apps requiring session revocation (admin panels, banking).
- When configuring OAuth providers, add the desired providers (Google, GitHub, Discord, etc.) and handle the `signIn` callback to control access and account linking.
- When customizing sessions, always add `user.id` to the `session` callback since it is not included by default, and add any custom fields like `role` or `tenantId` in the JWT callback.
- When protecting routes, use `auth()` in Server Components, Route Handlers, and Server Actions; do not rely solely on middleware for authorization.
- When building custom login pages, set `pages: { signIn: "/login" }` in the config to replace the default Auth.js page with a branded UI.
- When integrating a database, use the appropriate adapter (`@auth/prisma-adapter`, `@auth/drizzle-adapter`, `@auth/mongodb-adapter`) or implement the `Adapter` interface for custom databases.

## Examples

### Example 1: Add Google and GitHub OAuth to a Next.js app

**User request:** "Set up Auth.js with Google and GitHub login in my Next.js app"

**Actions:**
1. Install `next-auth` and configure `auth.ts` with Google and GitHub providers
2. Set up the session callback to include `user.id` and `user.role`
3. Add `middleware.ts` to protect authenticated routes
4. Create a custom login page with provider sign-in buttons

**Output:** A Next.js app with OAuth login via Google and GitHub, protected routes, and a custom sign-in page.

### Example 2: Add role-based access control with database sessions

**User request:** "Implement admin and user roles with database sessions"

**Actions:**
1. Set up Prisma adapter with a User model that includes a `role` field
2. Configure database session strategy in `auth.ts`
3. Add the `role` to the JWT and session callbacks
4. Create middleware that checks `session.user.role` before granting access to admin routes

**Output:** A role-based auth system where admins and users see different content, backed by database sessions for revocability.

## Guidelines

- Always customize the `session` callback to include `user.id` since it is not included by default.
- Protect API routes and Server Actions with `auth()` rather than relying only on middleware.
- Store provider tokens in the JWT callback if you need to call provider APIs (GitHub, Google Calendar).
- Keep `AUTH_SECRET` in environment variables and rotate periodically; never expose session secrets.
- Use `Scrypt` or `Argon2id` for password hashing in credentials-based flows.
- Handle errors gracefully: implement error pages for `OAuthCallbackError` and `AccessDenied` scenarios.
