---
title: "Migrate Legacy Codebase with AI"
slug: migrate-legacy-codebase
description: "Migrate legacy codebases to modern frameworks with AI-generated tests to prevent regressions and security audits to harden the new code."
skills: [code-migration, test-generator, security-audit]
category: development
tags: [migration, legacy-code, testing, security, modernization]
---

# Migrate Legacy Codebase with AI

## The Problem

Your team maintains a 65,000-line Express.js 4 API from 2018 -- callback-based, CommonJS, an unmaintained ORM, Node 14 with no security support. Three key dependencies have no maintainers and CVEs pile up quarterly. The last npm audit showed 47 vulnerabilities, 12 of them high severity, and the fixes require upgrading to packages that dropped callback support entirely.

The obvious answer is "just rewrite it," but this API processes $2.3M in monthly transactions. A rewrite takes 6 months, and in 6 months the team ships zero features while competitors iterate weekly. Incremental migration is the only realistic path -- but without tests, you won't know what breaks until customers report it. And migrating without a security review just moves old vulnerabilities into new code, or worse, introduces new ones that the old code didn't have.

## The Solution

The **code-migration** skill converts legacy patterns -- callbacks to async/await, CommonJS to ESM, outdated ORMs to Prisma. The **test-generator** skill creates baseline tests before migration to catch regressions. The **security-audit** skill reviews migrated code for vulnerabilities introduced during conversion. Together, they make it safe to modernize one module at a time.

## Step-by-Step Walkthrough

### Step 1: Generate Baseline Tests Before Touching Anything

```text
Generate snapshot tests for the payment, auth, and order modules. Capture
current input/output behavior for regression detection during migration.
```

Before changing a single line of code, baseline tests lock down the existing behavior. These tests verify what the code does, not how it does it -- so they'll still pass after callbacks become async/await and Waterline becomes Prisma:

| Test Suite | Tests | Coverage |
|-----------|-------|----------|
| `tests/baseline/payment.test.js` | 28 | Charge creation, refunds, webhooks, expired cards, duplicate charges |
| `tests/baseline/auth.test.js` | 22 | Login, registration, token refresh, brute force lockout |
| `tests/baseline/orders.test.js` | 19 | Order creation, status transitions, inventory reservation |

69 baseline tests total, all passing against the current code. These are the safety net for everything that follows.

### Step 2: Migrate the First Module

```text
Migrate src/services/payment.js from callbacks to async/await. Convert
require() to ESM. Replace Waterline queries with Prisma. Keep the same
API contracts.
```

The payment module goes first because it has the best test coverage and the most callback nesting -- 8 levels deep in some charge-creation flows.

The migration touches every line but preserves every behavior:

- **34 callback chains** become async/await (8 nesting levels flatten to 3)
- **12 `require()` calls** become ESM imports
- **18 Waterline queries** become Prisma client calls
- **Callback `err` patterns** become try/catch with typed errors

Before: 342 lines, cyclomatic complexity 34. After: 241 lines, cyclomatic complexity 18. The code is 30% shorter because async/await eliminates the deep nesting, and Prisma's type-safe queries replace verbose Waterline chainables. More importantly, the migrated code has TypeScript types flowing through every function -- a Prisma query returns a typed result, so downstream code gets autocomplete and compile-time error checking that the old callback code never had.

Here's what the transformation looks like in practice -- a charge creation flow that was 8 levels of callbacks deep:

```typescript
// Before: callback hell with error-first pattern
db.Payment.create(chargeData, function(err, payment) {
  if (err) return callback(err);
  stripe.charges.create({ amount: payment.amount }, function(err, charge) {
    if (err) return callback(err);
    db.Payment.update(payment.id, { stripeId: charge.id }, function(err) {
      if (err) return callback(err);
      callback(null, charge);
    });
  });
});

// After: linear async/await with typed errors
const payment = await prisma.payment.create({ data: chargeData });
const charge = await stripe.charges.create({ amount: payment.amount });
await prisma.payment.update({ where: { id: payment.id }, data: { stripeId: charge.id } });
return charge;
```

Running the baseline tests: 28/28 passing. The behavior is identical; only the implementation changed.

### Step 3: Migrate the Remaining Modules

```text
Migrate auth.js and orders.js using the same patterns. Run baseline tests
after each module.
```

Each module follows the same pattern: convert, then verify.

**auth.js** -- 21 callbacks become async/await. JWT handling modernizes from the aging `jsonwebtoken` library to `jose` (better algorithm support, ESM-native). Waterline User, Session, and Token models become Prisma calls. Baseline: 22/22 passing.

**orders.js** -- 26 callbacks become async/await. The trickiest conversion is inventory locking, which relied on Waterline's `.native()` escape hatch for MongoDB atomic operations. Prisma interactive transactions with proper isolation levels replace it cleanly. Baseline: 19/19 passing.

All 69 baseline tests passing. Zero regressions across three modules.

### Step 4: Security Audit the Migrated Code

```text
Run a security audit on the migrated modules. Focus on issues introduced
during migration — new ORM queries, async error handling, updated JWT library.
```

This is where the migration would normally introduce silent vulnerabilities. Swapping one library for another changes the defaults, and defaults are where security bugs hide.

The audit finds 7 issues, all introduced by the migration itself:

**Critical (1):**
- `auth.js:67` -- JWT audience claim not validated after jose migration. The old Waterline version checked `aud` manually; the migration dropped the check. Fixed.

**High (3):**
- `orders.js:112` -- Prisma transaction missing isolation level, enabling double-reserve on concurrent requests. Added `Serializable` isolation. Fixed.
- `payment.js:89` -- Webhook signature verification uses timing-unsafe string comparison after migration. Restored `crypto.timingSafeEqual`. Fixed.
- `auth.js:145` -- Password reset token stored plaintext in the new schema. The old code hashed it; the migration missed that detail. Added bcrypt hash. Fixed.

**Medium (3):** Two error handlers expose stack traces in production responses (the old callback error handlers caught everything; the new try/catch blocks let some errors propagate with full details). One Prisma query on the user profile endpoint returns the full user object including the password hash -- the old Waterline query had a `.select()` that excluded it, but the Prisma migration didn't carry that projection forward.

Every one of these issues was introduced by the migration, not by bad original code. The old code was actually secure in these areas -- it just used patterns that don't survive a library swap. This is exactly why a post-migration security audit isn't optional.

All 7 fixes applied. Baseline tests: 69/69 still passing -- the security fixes don't change the external behavior, they fix internal handling.

### Step 5: Generate Tests for the New Patterns

```text
Generate tests covering the new async patterns, Prisma transactions, and
jose JWT handling.
```

The baseline tests proved the migration didn't break existing behavior. New tests cover the patterns that didn't exist before:

| Test Suite | Tests | What It Covers |
|-----------|-------|---------------|
| `async-errors.test.js` | 11 | Promise rejection propagation, connection pool exhaustion, timeout handling |
| `prisma-transactions.test.js` | 8 | Isolation levels, rollback on failure, pool recovery after errors |
| `jose-jwt.test.js` | 6 | Audience validation, algorithm confusion attacks, key rotation |

Total: 94 tests (69 baseline + 25 new), all passing. Statement coverage on migrated modules: 81%.

## Real-World Example

A lead engineer at a 20-person logistics startup needed to migrate a 50,000-line Express 4 API off Node 14 before AWS Lambda dropped runtime support in 8 weeks. The API processed 400,000 shipment events daily -- downtime meant lost package visibility for enterprise clients.

Monday, the test-generator captured 82 baseline tests across 6 modules. That afternoon, code-migration converted the shipment tracking module from callbacks to async/await. By Wednesday, 4 modules were migrated with zero regressions. Thursday, the security-audit caught a critical issue: the migration accidentally removed rate limiting on webhook ingestion, enabling event flooding. Two-minute fix.

The migrated API deployed Friday with 112 tests providing confidence. Post-deployment monitoring showed a 23% reduction in p99 latency -- async/await eliminates the callback overhead and allows the event loop to schedule I/O more efficiently. Memory usage dropped 15% because callback chains were holding references longer than necessary.

The migration completed 5 weeks ahead of the Lambda deadline. More importantly, the test suite became the team's most valuable asset going forward -- it caught 4 regressions in subsequent PRs that would have reached production without it. The security audit pattern stuck too: every significant refactor now gets a post-migration security review as a matter of course.
