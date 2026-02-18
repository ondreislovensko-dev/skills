---
title: "Set Up Authentication and Authorization for a Web Application"
slug: set-up-auth-system
description: "Implement a complete auth system with OAuth login, JWT tokens, and role-based access control from scratch."
skills: [auth-system-setup, jwt-handler, security-audit]
category: development
tags: [authentication, authorization, oauth, jwt, rbac]
---

# Set Up Authentication and Authorization for a Web Application

## The Problem

Elena is a solo developer building a SaaS project management tool. The Express API and React frontend are working -- users can create projects, manage tasks, assign teammates. There's just one problem: authentication is a hardcoded user ID in the request headers. Every request pretends to be User 1. She needs to ship a beta to 20 pilot users next week, and "everyone is the same person" isn't going to cut it.

Adding auth to an existing application is one of the most error-prone tasks in backend development. She needs OAuth integration with Google so users don't have to create yet another password, JWT tokens with refresh rotation so sessions don't die every 15 minutes, and granular role-based access control -- admins manage users, managers manage projects, members view and update their own tasks. All of it has to be wired together correctly. A single mistake means leaked tokens, privilege escalation, or locked-out users. Most teams spend 2-3 weeks getting this right, and still ship vulnerabilities. Elena has five days.

## The Solution

Use the **auth-system-setup** skill to scaffold the full auth architecture, **jwt-handler** to implement secure token generation and validation with refresh rotation, and **security-audit** to verify the implementation against OWASP guidelines before it touches production.

## Step-by-Step Walkthrough

### Step 1: Define the Auth Requirements

Elena starts by describing what she needs -- the stack, the providers, and the permission model.

```text
I'm building a project management app with a Node.js/Express backend and PostgreSQL.
I need: Google OAuth login, JWT access/refresh tokens, and three roles -- admin, manager, member.
Admins manage users, managers manage projects, members view and update tasks assigned to them.
Set up the full auth system.
```

### Step 2: Scaffold the OAuth Flow

Google OAuth with PKCE (Proof Key for Code Exchange) prevents authorization code interception -- a critical security measure for public clients. The flow: user clicks "Sign in with Google," gets redirected to Google's consent screen, returns with an authorization code, and the server exchanges it for user info and issues a JWT.

Five files establish the foundation:

```typescript
// auth/providers/google.ts -- OAuth 2.0 with PKCE flow
// Handles: redirect to Google, callback processing, user creation/lookup

// auth/middleware/authenticate.ts -- JWT verification middleware
// Reads Bearer token, verifies signature and expiry, attaches user to req

// auth/middleware/authorize.ts -- Role-based access guard
// Higher-order middleware: authorize('admin', 'manager')

// auth/services/token.service.ts -- Token pair generation
// Access token: 15 minutes, RS256 signed
// Refresh token: 7 days, stored in DB with rotation support

// migrations/001_create_users_and_roles.sql
// User table, role table, permission table, refresh_tokens table
```

The complete OAuth flow: `/auth/google` redirects to Google's consent screen, Google calls back to `/auth/google/callback` with an authorization code, the server exchanges it for user info, creates or finds the user in PostgreSQL, and issues a JWT pair.

### Step 3: Configure Role-Based Access Control

Three roles with granular permissions and row-level filtering so members only see what belongs to them.

```text
Add RBAC with these permissions:
- admin: users.read, users.write, users.delete, projects.*, tasks.*
- manager: projects.create, projects.update, tasks.*, members.read
- member: tasks.read, tasks.update (own only), projects.read
Include row-level filtering so members only see their assigned tasks.
```

The permission matrix maps cleanly to middleware:

```typescript
// Route protection with granular permissions
router.delete('/users/:id', authorize('users.delete'), UserController.remove);
router.get('/tasks', authorize('tasks.read'), filterByRole, TaskController.list);

// filterByRole middleware adds a WHERE clause:
// Admin/Manager: no filter (see everything)
// Member: WHERE assignee_id = req.user.id
```

Row-level security is the piece most auth tutorials skip. Without it, a member who guesses a task ID can view anyone's work. The `filterByRole` middleware intercepts list queries and injects the appropriate filter based on the user's role. Fourteen test cases verify every role boundary -- admin can delete users, manager cannot; member can update their own tasks but gets a 403 on someone else's.

### Step 4: Harden the Token Lifecycle

JWTs are only as secure as their lifecycle management. Refresh token rotation, reuse detection, and proper cookie settings prevent the most common attack vectors.

```text
Review the JWT implementation for security issues. I want refresh token rotation
with reuse detection, proper token revocation on logout, and secure cookie settings.
```

The security review hardens five areas:

- **One-time rotation**: Each refresh invalidates the old token immediately. A refresh token can only be used once -- if it's intercepted and replayed, the replay fails.
- **Token family tracking**: If a revoked refresh token is reused (indicating theft), all tokens in that family get invalidated. Both the attacker and the legitimate user have to re-authenticate, but the attacker can't get in.
- **Storage separation**: Access tokens live in memory only (never localStorage, never cookies). Refresh tokens go in `httpOnly` secure cookies with `SameSite=Strict` -- invisible to JavaScript, immune to XSS.
- **Logout revocation**: The logout endpoint revokes all active refresh tokens for the user, not just the current one. Signing out means signing out everywhere.
- **Rate limiting**: The `/auth/refresh` endpoint allows a maximum of 10 requests per minute per user. A legitimate client refreshes once every 15 minutes; anything faster is suspicious.

Eight additional test cases cover rotation and reuse detection, including the scenario where an attacker replays a stolen token after the legitimate user has already rotated it.

### Step 5: Run a Security Audit Against OWASP

Before shipping, the auth system gets audited against the OWASP Top 10 and common auth-specific vulnerabilities.

```text
Run a security audit on the auth implementation. Check against OWASP top 10
and common auth vulnerabilities.
```

Audit results:

| Check | Status | Detail |
|---|---|---|
| OAuth state parameter (CSRF prevention) | Pass | Random state generated per request, validated on callback |
| PKCE for OAuth | Pass | No authorization code interception possible |
| Refresh token rotation with reuse detection | Pass | Token family tracking active |
| No password storage | Pass | OAuth-only flow eliminates password-related vulnerabilities |
| Role checks at middleware level | Pass | Authorization happens before business logic, not inside it |
| Rate limiting on callback endpoint | Warning | Added brute-force protection to `/auth/google/callback` |
| Session fingerprinting | Warning | Added IP + User-Agent binding as an optional security layer |

Five passed, two warnings, zero critical issues. Both warnings get patched immediately -- the callback rate limit and session fingerprinting go into `auth.routes.ts` the same afternoon.

## Real-World Example

Elena starts Monday morning with a hardcoded User ID and five days until her beta launch. By Monday afternoon, the OAuth flow is working -- she can sign in with Google and see her actual name in the app. Tuesday morning, RBAC goes live: she invites two colleagues, one as a manager and one as a member, and they can only see what they're supposed to see. The member tries to access the admin panel and gets a clean 403.

Wednesday is token hardening day. Refresh rotation, reuse detection, secure cookies -- the pieces that aren't glamorous but prevent the security incidents that make the news. Thursday, the security audit catches the two warnings and they're patched by lunch.

Friday, 20 pilot users get their invitations. The auth system handles Google OAuth, issues properly scoped JWTs, enforces role boundaries at every endpoint, and rotates refresh tokens on every use. It took four days instead of the two weeks Elena had originally budgeted, and the security audit gives her confidence that she's not shipping a vulnerability to her first paying customers.
