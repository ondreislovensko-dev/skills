---
title: "Secure an API with Rate Limiting and JWT Authentication"
slug: secure-api-with-rate-limiting-and-jwt
description: "Build a production-ready API security layer with JWT-based authentication, role-based access control, and intelligent rate limiting to protect against abuse."
skills: [rate-limiter, jwt-handler, auth-system-setup]
category: development
tags: [api-security, jwt, rate-limiting, authentication, authorization]
---

# Secure an API with Rate Limiting and JWT Authentication

## The Problem

Marta is building a public-facing REST API for her team's SaaS product. Right now, anyone can hit any endpoint -- there's no authentication, no authorization, and no throttling. The API is fully functional, serving about 15 endpoints, but it's wide open. Before launch, she needs JWT-based auth with role-based permissions, and rate limiting so a single client can't hammer the API and degrade service for everyone else. She's seen what happens when an unprotected API meets the real world, and she'd rather not learn that lesson firsthand.

## The Solution

Use **auth-system-setup** to scaffold the authentication flow (registration, login, password hashing), **jwt-handler** to issue and verify tokens with role claims, and **rate-limiter** to add per-user and per-IP throttling. Together, these three skills produce a layered security setup that's ready for production.

## Step-by-Step Walkthrough

### Step 1: Scaffold the Authentication System

Registration, login, email verification -- the foundation everything else builds on.

```text
I have an Express.js API with about 15 endpoints. I need user registration
and login with bcrypt password hashing, email verification tokens, and
a clean middleware pattern I can apply to protected routes. Use PostgreSQL
for the user store.
```

Five files establish the auth foundation:

- **`auth/user.model.ts`** -- User table schema with `id`, `email`, `password_hash`, `role`, `email_verified`, and `created_at`
- **`auth/register.ts`** -- `POST /auth/register` validates email format and password strength (minimum 10 characters, mixed case, at least one number), hashes with bcrypt at 12 rounds, assigns `role='viewer'` by default, and sends a verification token (SHA-256, expires in 24 hours)
- **`auth/login.ts`** -- `POST /auth/login` verifies credentials and rejects unverified accounts with a clear error message. Returns a JWT on success.
- **`auth/verify-email.ts`** -- `GET /auth/verify?token=xxx` marks the account verified and invalidates the token
- **`migrations/001_create_users.sql`** -- Database migration for the user and verification tables

The middleware stub (`auth/middleware.ts`) is ready for JWT logic in the next step.

### Step 2: Configure JWT Token Issuance and Verification

Short-lived access tokens for API calls, long-lived refresh tokens for session continuity, and revocation support for security incidents.

```text
Set up JWT handling. I need access tokens (short-lived, 15 minutes) and
refresh tokens (7 days, stored in DB so I can revoke them). Include the
user's role in the access token claims. Roles are: viewer, editor, admin.
```

The token service (`auth/jwt.ts`) implements four operations:

```typescript
// Issue a 15-minute access token with role claim
issueAccessToken(user): {
  // Payload: { sub: user.id, role: user.role, iat, exp }
  // Algorithm: RS256 with 2048-bit key pair
}

// Issue an opaque refresh token stored in the database
issueRefreshToken(user): {
  // crypto.randomBytes(64).toString('hex')
  // Stored as hash in refresh_tokens table (user_id, token_hash, expires_at)
  // Expiry: 7 days
}

// Validate signature and expiration
verifyAccessToken(token): decoded payload or rejection

// Rotate: invalidate old token, issue new pair
// Detects reuse of revoked tokens -> revokes entire token family
rotateRefreshToken(oldToken): { newAccessToken, newRefreshToken }
```

The refresh token rotation with reuse detection is the key security feature. If an attacker steals a refresh token and the legitimate user also tries to use it, the reuse triggers and all tokens in that family get revoked. Both parties have to re-authenticate, but the attacker is locked out.

The `requireAuth` middleware reads the Bearer token from the Authorization header, verifies it, and attaches the decoded user to `req.user`. The `requireRole('admin')` higher-order middleware checks `req.user.role` against the allowed roles.

Key pair files (`jwt-private.pem`, `jwt-public.pem`) go in `config/` and are added to `.gitignore` -- generated per environment, never committed.

### Step 3: Apply Role-Based Access Control to Endpoints

```text
Apply the auth middleware to my routes. Here's the access pattern:
  - GET /projects -- any authenticated user
  - POST /projects -- editor or admin
  - DELETE /projects/:id -- admin only
  - GET /analytics -- admin only
  - GET /public/status -- no auth required
```

The middleware chain makes permissions explicit and readable:

```typescript
// Any authenticated user can list projects
router.get('/projects', requireAuth, projectController.list);

// Only editors and admins can create
router.post('/projects', requireAuth, requireRole('editor', 'admin'), projectController.create);

// Only admins can delete
router.delete('/projects/:id', requireAuth, requireRole('admin'), projectController.delete);

// Analytics restricted to admins
router.get('/analytics', requireAuth, requireRole('admin'), analyticsController.get);

// Public endpoint -- no middleware
router.get('/public/status', statusController.get);
```

Error responses are clear and consistent: missing token returns `401 Authentication required`, expired token returns `401 Token expired`, insufficient role returns `403 Insufficient permissions`. Each response includes enough information for the client to handle it correctly without leaking internal details.

### Step 4: Implement Rate Limiting Per User and Per IP

```text
Add rate limiting. I want:
  - Global: 100 requests per minute per IP for unauthenticated routes
  - Authenticated: 300 requests per minute per user ID
  - Login endpoint: 5 attempts per 15 minutes per IP (brute force protection)
  - Admin endpoints: no rate limit
Use Redis as the backing store.
```

Three limiter configurations in `middleware/rate-limiter.ts`, all backed by Redis with a sliding window algorithm (smoother than fixed windows):

**Global limiter** -- keyed on `req.ip`, 100 requests per 60-second window. Applied to all public routes. Response headers include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` so clients can self-throttle.

**Authenticated limiter** -- keyed on `req.user.id` (applied after `requireAuth`), 300 requests per 60-second window. Skips the limit entirely when `req.user.role === 'admin'` -- admins running data exports shouldn't hit artificial ceilings.

**Login limiter** -- keyed on `req.ip`, 5 attempts per 15-minute window. This is the brute-force protection. After 5 failed attempts, the response is `429 Too many login attempts. Try again in N minutes.` with a `Retry-After` header.

Route application:

```typescript
app.use('/public', globalLimiter);
app.use('/auth/login', loginLimiter);
app.use('/projects', requireAuth, authenticatedLimiter);
app.use('/analytics', requireAuth, requireRole('admin'));  // no limiter
```

Redis key pattern: `rl:{type}:{key}` with TTL matching the window duration. If Redis goes down, the limiters fail open (allow requests) rather than locking out all users -- a deliberate design choice that prioritizes availability over strict enforcement during infrastructure issues.

### Step 5: Test the Full Security Stack

```text
Generate a test suite that verifies the auth flow end-to-end:
registration, login, token refresh, role enforcement, and rate
limiting. Use Jest and supertest.
```

The test suite (`tests/auth-security.test.ts`) covers 18 cases across four areas:

**Registration** (4 tests): Successful registration with valid credentials, duplicate email rejection, weak password rejection, and verification token generation.

**Login and JWT** (5 tests): Valid login returns both tokens, unverified email gets rejected, wrong password gets rejected, access token expires after 15 minutes (mocked clock), and refresh token rotation issues a new pair while invalidating the old one.

**Role-based access** (4 tests): Viewer can `GET /projects`, viewer cannot `POST /projects` (returns 403), editor can `POST /projects`, and only admin can `DELETE /projects/:id`.

**Rate limiting** (5 tests): Returns 429 after 100 unauthenticated requests, returns 429 after 5 login attempts in 15 minutes, authenticated user gets the 300 request per minute allowance, admin bypasses the authenticated rate limit, and rate limit headers are present in all responses.

All tests use `ioredis-mock` for speed and a separate PostgreSQL schema that resets between suites. The full suite runs in under 8 seconds.

## Real-World Example

Dani runs a small analytics platform with three tiers of API consumers: a free plan, a paid plan, and enterprise. After a bot scraped his entire dataset through the unauthenticated endpoint -- downloading 18 months of data in a single afternoon -- he used this approach to lock things down.

Registration and JWT auth went in first, gating every data endpoint behind authentication. Then he extended the rate limiter tiers beyond the basic three: free-plan users get 60 requests per minute, paid users get 600, and enterprise gets 3,000 -- all read from the JWT claims, so upgrading a customer's plan takes effect on their next token refresh without any code changes.

The login brute-force protection caught two credential-stuffing attempts in the first week -- automated scripts cycling through leaked password databases. Both were blocked after 5 attempts. The whole security layer shipped in an afternoon, and Dani sleeps better knowing his API isn't a free buffet anymore.
