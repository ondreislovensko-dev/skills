---
title: "Automate API Contract Testing to Prevent Breaking Changes"
slug: automate-api-contract-testing
description: "Set up consumer-driven contract tests between services so API changes never break downstream clients silently."
skills: [api-tester, test-generator, cicd-pipeline]
category: development
tags: [api-contracts, testing, microservices, breaking-changes, pact]
---

# Automate API Contract Testing to Prevent Breaking Changes

## The Problem

A backend team pushes a "minor" API change — renaming a field from `userName` to `user_name`. Three frontend apps break in production. Nobody ran integration tests because they take 40 minutes and flake constantly. The team has 14 internal APIs, each consumed by 2-5 services, and zero contract coverage. Every sprint ships at least one unintended breaking change.

The fundamental issue is asymmetric knowledge: the provider team knows what they changed, but they have no idea which consumers depend on which fields. A field that looks unused might be the only thing holding the billing dashboard together.

## The Solution

Use **api-tester** to map every endpoint's current request/response shape, **test-generator** to produce consumer-driven contract tests for each client-provider pair, and **cicd-pipeline** to run contracts on every PR so breaking changes get caught before merge.

## Step-by-Step Walkthrough

### Step 1: Map the Existing API Surface

```text
Here's our users service OpenAPI spec (paste or link). Crawl every endpoint,
document request/response schemas, and flag any fields that have inconsistent
naming conventions (camelCase vs snake_case mix). List every consumer service
that calls each endpoint — I'll confirm the list.
```

The spec contains 23 endpoints across 4 resource groups. Before writing any tests, the inconsistencies need documenting — 6 fields mix naming conventions, which is how the `userName` versus `user_name` disaster happened in the first place:

| Endpoint | Inconsistent Fields | Used By |
|---|---|---|
| `GET /users/{id}` | `userName` (camelCase) | billing, dashboard, mobile |
| `POST /users/{id}/subscription` | `plan_type` (snake_case) | billing |
| `GET /users/{id}/activity` | `lastLogin` (camelCase) | dashboard |

The full dependency matrix shows which services consume which endpoints — 47 consumer-endpoint pairs total. This is the map that did not exist before, and it is the reason nobody could predict what would break.

### Step 2: Generate Consumer Contract Tests

```text
For each consumer-provider pair in the matrix, generate Pact contract tests.
The billing service consumes GET /users/{id} and POST /users/{id}/subscription.
The dashboard consumes GET /users, GET /users/{id}, and GET /users/{id}/activity.
The mobile API gateway consumes all user endpoints. Generate provider-side
verification tests too.
```

Each consumer gets tests that describe exactly what it expects from the provider. Here is what the billing service's contract looks like:

```typescript
// billing-service/tests/contracts/users.pact.spec.ts
describe('Users API contract', () => {
  it('returns user with subscription fields', async () => {
    await provider.addInteraction({
      state: 'user 123 exists with active subscription',
      uponReceiving: 'a request for user 123',
      withRequest: {
        method: 'GET',
        path: '/users/123',
      },
      willRespondWith: {
        status: 200,
        body: {
          id: like('123'),
          userName: like('jane.doe'),        // Billing depends on this exact field name
          email: like('jane@example.com'),
          subscription: {
            plan_type: like('enterprise'),
            status: like('active'),
          },
        },
      },
    });
  });
});
```

The critical detail: the billing service's contract explicitly specifies `userName` (camelCase). If anyone renames it to `user_name`, the contract fails *before the code ships*.

In total: **34 contract test files** — one per consumer-endpoint combination on the consumer side, plus provider verification tests that run all consumer pacts together. The provider cannot ship a change that breaks any consumer.

### Step 3: Set Up the Contract Broker and CI Integration

```text
Configure a Pact broker using the free Pactflow starter. Add CI pipeline steps
so that: consumer tests run on consumer PRs, provider verification runs on
provider PRs, and deployment is blocked if any contract is broken. Use GitHub
Actions. The provider repo is users-service and consumers are billing-service,
dashboard-app, and mobile-gateway.
```

The CI integration creates a closed loop where contract violations block deployment:

**Consumer side** (billing-service, dashboard-app, mobile-gateway):

```yaml
# .github/workflows/contracts.yml
- name: Run consumer contract tests
  run: npx jest --testPathPattern=pact
- name: Publish pacts to broker
  run: npx pact-broker publish ./pacts --consumer-app-version=${{ github.sha }}
```

**Provider side** (users-service):

```yaml
# .github/workflows/contracts.yml
- name: Verify all consumer contracts
  run: npx jest --testPathPattern=pact-verification
- name: Can I deploy?
  run: npx pact-broker can-i-deploy --pacticipant=users-service --version=${{ github.sha }}
```

The `can-i-deploy` check is the enforcement mechanism. It queries the broker: "Given my latest code, will any consumer break?" If the answer is yes, the deployment is blocked. No exceptions, no "I'll fix it later."

### Step 4: Handle the First Breaking Change Safely

```text
I need to rename the "userName" field to "username" across all endpoints.
Generate a migration plan: add the new field alongside the old one, update
consumer contracts one by one, then deprecate the old field. Show me the
exact contract test changes for each step.
```

This is the exact scenario that caused the outage. With contracts in place, the rename becomes a controlled three-phase migration instead of a surprise breaking change:

**Phase 1: Provider adds the alias (both fields returned)**

```typescript
// users-service — response now includes both fields
{
  userName: 'jane.doe',   // Keep for existing consumers
  username: 'jane.doe',   // New canonical field
}
```

All existing consumer contracts still pass because `userName` is still present. The new `username` field is additive — it breaks nothing.

**Phase 2: Consumers migrate one by one**

Each consumer updates its contract to expect `username` instead of `userName`, at its own pace. The billing team does it on Monday, the dashboard team on Wednesday, the mobile team the following week. Each migration is a small, safe PR.

```typescript
// billing-service — updated contract
willRespondWith: {
  body: {
    username: like('jane.doe'),  // Changed from userName
  },
}
```

**Phase 3: Provider removes the old field**

Once the broker shows that every consumer's latest contract expects `username`, the provider removes `userName`. If any consumer is still referencing the old field, the `can-i-deploy` check blocks the removal.

Total time: 2-3 weeks, zero breakage, full confidence at every step.

### Step 5: Add Contract Coverage Reporting

```text
Add a CI step that reports contract coverage: what percentage of endpoints
have consumer contracts, which endpoints are untested, and which consumers
are missing contracts. Output as a markdown table in PR comments.
```

A coverage script cross-references the OpenAPI spec with published pacts and posts a report on every PR:

| Resource Group | Endpoints | Covered | Coverage |
|---|---|---|---|
| Users | 8 | 8 | 100% |
| Subscriptions | 5 | 5 | 100% |
| Activity | 6 | 6 | 100% |
| Admin | 4 | 4 | 100% |
| **Total** | **23** | **23** | **100%** |

34 out of 34 consumer-endpoint pairs tested. Every endpoint has at least one consumer contract, and every consumer has contracts for every endpoint it uses. When a new endpoint gets added without contracts, the coverage report flags it immediately.

## Real-World Example

A platform engineer at a 30-person fintech runs 14 internal APIs. Every two weeks, a field rename or response shape change breaks a downstream service in staging — sometimes in production. The team spends 6-8 hours per sprint debugging integration failures, and the post-mortem always says the same thing: "we didn't know anyone was using that field."

She maps all 14 APIs and their consumers, producing a 47-row dependency matrix that makes the invisible dependencies visible for the first time. The agent generates 89 contract test files across all consumer-provider pairs. CI pipelines enforce contracts on every PR.

In the first sprint with contracts, 3 breaking changes are caught before merge — all cases where a provider team had no idea a consumer depended on a specific field name or response shape. Over 6 weeks, integration failures drop from 4 per sprint to zero. The team reclaims 6+ hours per sprint that was being burned on "why did this break?" investigations.
