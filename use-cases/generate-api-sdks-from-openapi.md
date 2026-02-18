---
title: "Generate API SDKs from OpenAPI Specs"
slug: generate-api-sdks-from-openapi
description: "Turn your OpenAPI specification into typed SDKs for multiple languages with documentation, tests, and CI publishing."
skills: [coding-agent, test-generator, markdown-writer]
category: development
tags: [SDK, OpenAPI, code-generation, API, developer-experience]
---

# Generate API SDKs from OpenAPI Specs

## The Problem

Your API has 31 endpoints and a well-maintained OpenAPI spec. Customers keep asking for SDKs -- the Python team wants a Python client, the JavaScript developers want a typed npm package, and the Go team needs something idiomatic. Hand-writing SDKs for 3 languages means maintaining 3 parallel codebases that drift out of sync every time you add an endpoint.

Existing generators like openapi-generator produce code that compiles but reads like it was written by a machine -- verbose, unidiomatic, and missing the error handling patterns developers expect. The generated code needs so much cleanup that maintaining it becomes a full-time job. You need SDKs that feel hand-written but update automatically when your spec changes.

## The Solution

Using **coding-agent** to generate idiomatic SDK code from your OpenAPI spec, **test-generator** to create comprehensive test suites, and **markdown-writer** to produce SDK documentation with examples -- the workflow produces publish-ready packages that stay in sync with your API.

## Step-by-Step Walkthrough

### Step 1: Analyze the OpenAPI Spec

```text
Parse our openapi.yaml. Summarize the API surface: endpoints, models, auth patterns, and pagination style. Identify anything that needs special SDK handling.
```

The spec analysis maps out the full API surface and flags four patterns that need special SDK treatment:

| Aspect | Details |
|---|---|
| **Endpoints** | 31 across 6 groups (Orders, Products, Users, Webhooks, Reports, Events) |
| **Models** | 24 schemas |
| **Auth** | JWT bearer tokens + API key header |
| **Pagination** | Cursor-based with `next_cursor` field |
| **Errors** | RFC 7807 problem details |
| **Rate limiting** | 429 status + `Retry-After` header |

**Special handling needed:**
- Bulk operations accept arrays of up to 1,000 items -- SDKs need chunking
- Report generation is async (POST returns a job ID, poll for results) -- SDKs need a convenience method that waits for completion
- Events endpoint supports Server-Sent Events -- SDKs need streaming support
- Large export endpoints return paginated CSVs -- SDKs need streaming file download

### Step 2: Generate the TypeScript SDK

```text
Generate a TypeScript SDK for our API. Use fetch, full type safety, automatic pagination, retry on 429, and idiomatic error handling. Structure it as a publishable npm package.
```

The generated package is structured for immediate publishing:

```
sdks/typescript/
  src/client.ts        -- Main class with auth, retry on 429, auto-pagination
  src/resources/        -- Typed methods for all 6 resource groups
  src/types/            -- 24 TypeScript interfaces + typed error classes
  package.json          -- ESM + CJS dual output, ready to publish
  tsconfig.json
```

The API surface feels natural to TypeScript developers:

```typescript
import { ApiClient } from '@company/api-sdk';

const client = new ApiClient({ apiKey: 'sk_...' });

// Auto-pagination — iterate through all results without managing cursors
for await (const order of client.orders.listAll()) {
  console.log(order.total);
}

// Typed errors — catch specific failure modes
try {
  await client.orders.create({ productId: 'prod_123', quantity: 1 });
} catch (e) {
  if (e instanceof RateLimitError) {
    // Automatic retry already happened 3 times — this is a real problem
  }
  if (e instanceof ValidationError) {
    console.log(e.fields); // { quantity: "must be positive" }
  }
}
```

Rate limiting is handled transparently: the client reads the `Retry-After` header, waits, and retries up to 3 times before surfacing the error. Developers never write retry logic.

### Step 3: Generate the Python SDK

```text
Generate a Python SDK using httpx for async support, Pydantic models, and Pythonic conventions. Package with pyproject.toml for PyPI publishing.
```

The Python SDK follows the same structure but uses Python conventions throughout:

```
sdks/python/
  src/api_client/client.py       -- Sync and async clients with httpx
  src/api_client/resources/      -- Type-hinted methods for all resources
  src/api_client/models/         -- 24 Pydantic models with validation
  pyproject.toml                 -- Poetry config, ready for PyPI
```

Both sync and async patterns work out of the box:

```python
from api_client import ApiClient, AsyncApiClient

# Synchronous usage
client = ApiClient(api_key="sk_...")
for order in client.orders.list_all():
    print(order.total)

# Async usage
async with AsyncApiClient(api_key="sk_...") as client:
    order = await client.orders.create(product_id="prod_123", quantity=1)
    print(order.id)
```

Pydantic models provide runtime validation and IDE autocompletion. If the API returns a field your SDK version doesn't know about, Pydantic ignores it instead of crashing -- forward compatibility by default.

### Step 4: Generate Test Suites for Both SDKs

```text
Create test suites for both SDKs. Use recorded HTTP fixtures so tests run without a live API. Cover auth, CRUD, pagination, error handling, and retries.
```

Both test suites use recorded HTTP fixtures so they run fast and don't need a live API server:

| SDK | Tests | Coverage | Framework |
|---|---|---|---|
| TypeScript | 42 tests | 94% | vitest + MSW for HTTP mocking |
| Python | 38 tests | 91% | pytest + pytest-httpx |

The test fixtures are shared between both SDKs in a common `tests/fixtures/` directory -- same JSON responses, different test harnesses. When you add a new endpoint, you record the fixture once and both test suites can use it.

### Step 5: Generate Documentation and Publish Pipeline

```text
Create README docs for both SDKs with installation, quickstart, and per-resource examples. Add CI pipelines to publish on tag.
```

Each SDK gets a README with installation instructions, quickstart code, and examples for every resource group. The CI pipelines handle the full publish lifecycle:

```yaml
# .github/workflows/sdk-typescript.yml — publish on tag
on:
  push:
    tags: ['v*-ts']
jobs:
  publish:
    steps:
      - run: npm test          # 42 tests must pass
      - run: npm run build     # Compile TypeScript
      - run: npm publish       # Push to npm registry

# .github/workflows/sdk-sync.yml — keep SDKs in sync with spec
on:
  push:
    paths: ['openapi.yaml']
jobs:
  sync:
    steps:
      - run: regenerate-sdks   # Rebuild from updated spec
      - run: open-pr-if-diff   # Auto-PR if anything changed
```

The sync workflow is the key to long-term maintenance: every change to `openapi.yaml` triggers a regeneration of both SDKs and opens a PR if anything changed. SDKs never drift from the spec.

## Real-World Example

Tomas, the API lead at a 20-person developer tools startup, was losing deals because competitors had SDKs and he didn't. His 31-endpoint API had a solid OpenAPI spec, but hand-writing SDKs for even 2 languages would take weeks. He'd tried openapi-generator -- the output compiled but felt foreign. The Python SDK used `requests` instead of `httpx`, had no async support, and error handling was a single catch-all exception class.

He ran the three-skill workflow on a Wednesday. The coding-agent produced a TypeScript SDK with auto-pagination, typed errors, and retry logic -- code his team would have been proud to write by hand. The Python SDK used Pydantic models and supported both sync and async patterns. The test-generator created 80 tests across both SDKs with recorded HTTP fixtures, catching 3 edge cases in the OpenAPI spec where the documented response didn't match what the API actually returned.

He published both SDKs on Thursday. Within a week, 3 customers who'd been using raw HTTP switched to the SDKs. Support tickets about API integration dropped 40%. The automated sync pipeline proved its worth on Friday -- he added a new endpoint to the API, and the pipeline regenerated both SDKs and opened a PR before he'd even thought about updating them manually.
