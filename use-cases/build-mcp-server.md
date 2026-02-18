---
title: "Build an MCP Server with AI"
slug: build-mcp-server
description: "Build a Model Context Protocol server, test its API endpoints, and generate a comprehensive test suite for reliable tool integration."
skills: [mcp-server-builder, api-tester, test-generator]
category: development
tags: [mcp, api, testing, ai-tools, server]
---

# Build an MCP Server with AI

## The Problem

Your team wants to expose internal tools -- inventory lookup, order tracking, customer records -- as MCP tools so AI assistants can query them directly. Instead of support agents switching between 4 dashboards to answer "where's my order?", they could ask Claude and get an answer in seconds.

But building an MCP server means handling the protocol spec correctly: JSON-RPC transport, tool schemas with proper Zod validation, structured error responses, and connection lifecycle management. And unlike a REST API where humans read error messages and adapt their requests, AI agents will call tools with unexpected inputs -- empty strings, wrong types, massive payloads, fields in the wrong format. A malformed response does not produce a helpful error message. The agent silently fails, and the user gets a bad answer with no indication that the tool call went wrong.

The protocol compliance requirements are strict enough that getting them mostly right is not good enough. A server that handles 95% of cases correctly but crashes on unknown notification types will work fine in testing and fail unpredictably in production.

## The Solution

Using the **mcp-server-builder**, **api-tester**, and **test-generator** skills, the agent scaffolds a production-ready MCP server with three tools, tests every endpoint with realistic requests and edge cases, fixes the bugs that surface during testing, and generates an automated test suite so regressions get caught before deployment.

## Step-by-Step Walkthrough

### Step 1: Scaffold the MCP Server

```text
Build an MCP server with three tools: inventory-lookup (search by SKU or name), order-status (track by ID), customer-search (find by email or phone). TypeScript with @modelcontextprotocol/sdk, PostgreSQL backend.
```

The scaffolded project:

```
mcp-warehouse-server/
  src/index.ts           # Server entry with stdio transport
  src/tools/inventory.ts # inventory-lookup (SKU, name, category search)
  src/tools/orders.ts    # order-status (by order ID or customer ID)
  src/tools/customers.ts # customer-search (email, phone, name)
  src/db.ts              # PostgreSQL with connection pooling
  src/schemas.ts         # Zod validation for all tool inputs
  src/errors.ts          # Typed errors (not-found, invalid-input, rate-limited)
```

Each tool has three layers: a Zod schema defining valid inputs (so invalid requests are rejected before hitting the database), a handler that queries PostgreSQL with parameterized queries (preventing SQL injection at the database level, not just validation), and typed error responses that give the AI agent enough context to try a different approach rather than silently failing.

The error design matters. When an agent searches for a non-existent order, it should get back a structured "order not found" response it can relay to the user -- not a generic 500 error that makes it guess what went wrong.

### Step 2: Test with Realistic Requests and Edge Cases

This is where most MCP servers break. An AI agent will not send tidy, well-formed requests every time. Testing needs to cover the messy reality of production usage:

```text
Test each MCP tool with realistic requests. Try normal lookups, empty results, invalid inputs, and edge cases like SQL injection and oversized payloads.
```

**inventory-lookup:**
- SKU `"WH-4521"` -- 1 result (Wireless Headphones, $79.99)
- Name `"cable"` -- 23 results, paginated correctly
- SKU `"NONEXISTENT-999"` -- returns `{ products: [], total: 0 }` (empty result, not an error)
- SQL injection attempt `"'; DROP TABLE--"` -- rejected by Zod validation before reaching the database
- 10,000-character input string -- rejected, max length 200 characters

**order-status:**
- `"ORD-78432"` -- complete order with 4 timeline events (placed, picked, shipped, delivered)
- Non-existent order -- structured MCP error: `{ code: -32602, message: "Order not found" }`
- Missing both order ID and customer ID -- **bug found:** returns HTTP 500 instead of a validation error

**customer-search:**
- Email lookup -- exact match returned, phone number masked in response for PII protection
- Phone lookup -- partial match with automatic E.164 normalization (`555-1234` becomes `+15551234`)
- Phone `"+1"` (too short to be valid) -- **bug found:** returns empty result instead of a validation error

Two bugs found and fixed in the first testing pass. All 16 test scenarios now passing. These are the kind of bugs that pass basic testing but cause confusion in production when agents get unexpected responses.

### Step 3: Verify Protocol Compliance

MCP servers need to handle protocol-level edge cases that never come up during normal tool usage but will crash the server when a client sends something unexpected:

```text
Test MCP protocol compliance: malformed JSON-RPC, unsupported methods, concurrent calls, connection handling.
```

| Test | Expected | Result |
|------|----------|--------|
| Malformed JSON body | Parse error (-32700) | Pass |
| Invalid method name | Method-not-found (-32601) | Pass |
| Missing required params | Invalid-params (-32602) | Pass |
| `tools/list` response | Correct schemas for all 3 tools | Pass |
| 10 concurrent tool calls | All resolve correctly | Pass (avg 45ms) |
| 500-product response | Streams without truncation | Pass |
| Unknown notification type | Ignore gracefully | **Fail: server crashes** |

The unknown notification crash is exactly the kind of bug that only surfaces in production. During testing, the client sends only expected notification types. But in the real world, different MCP clients may send notifications the server does not recognize. Without a catch-all handler, the server throws an unhandled exception and dies. Fix: add a default notification handler that logs and ignores unknown types. All 8 required protocol behaviors now verified.

### Step 4: Generate the Automated Test Suite

```text
Generate a test suite covering all tools, validation, error responses, and database edge cases. Vitest with test database.
```

The test suite covers 55 cases across 5 files:

| File | Tests | What it covers |
|------|-------|----------------|
| `tests/tools/inventory.test.ts` | 18 | Search by SKU/name/category, pagination, input validation, DB connection errors |
| `tests/tools/orders.test.ts` | 15 | Order lookup, compound ID validation, status timeline, cancelled order handling |
| `tests/tools/customers.test.ts` | 13 | Multi-field search, PII masking, phone normalization, email format validation |
| `tests/protocol/transport.test.ts` | 9 | JSON-RPC compliance, concurrent calls, reconnection, notification handling |
| `tests/setup.ts` | -- | Seed data: 50 products, 30 orders, 20 customers |

**55 tests, all passing. 87% statement coverage. 3.2-second run time.** The seed data creates a realistic test dataset -- not trivial single-row fixtures, but enough data to exercise pagination, partial matches, and edge cases like cancelled orders and expired products.

### Step 5: Finalize and Connect to Claude Desktop

```text
Add test scripts, README with setup guide, and verify the server works with Claude Desktop.
```

The `package.json` gets `"test": "vitest run"` and `"test:watch": "vitest"` for development. The README covers setup instructions, tool documentation with example inputs and outputs, and the Claude Desktop configuration:

```json
{
  "mcpServers": {
    "warehouse": {
      "command": "node",
      "args": ["dist/index.js"],
      "env": { "DATABASE_URL": "postgresql://..." }
    }
  }
}
```

Final verification: the server responds correctly to the `initialize` handshake, all 3 tools are callable from Claude Desktop with real queries, error responses are structured and informative, and the full 55-test suite passes clean with TypeScript strict mode enabled.

## Real-World Example

A platform engineer at a 50-person logistics company needed to give AI assistants access to warehouse, shipping, and returns data across 3 databases. Support agents were switching between 4 dashboards to answer every "where's my order?" question -- copying tracking numbers from one system, looking up shipment status in another, checking return eligibility in a third. Each ticket took an average of 6 minutes.

On Monday, the mcp-server-builder scaffolded 5 tools covering inventory, orders, shipments, returns, and customers. On Tuesday, the api-tester found 4 edge-case bugs that would have caused silent failures in production -- including pagination returning duplicate results when records were inserted between pages, and a null check crash when looking up cancelled orders with no shipment data. On Wednesday, the test-generator produced 72 tests at 84% coverage. On Thursday, the server went live in Claude Desktop for 8 support agents.

Ticket resolution dropped from 6 minutes to 2.5 minutes. Dashboard switching -- the thing that made every support interaction feel like a scavenger hunt -- disappeared entirely. The test suite caught 3 regressions in the first month of active development, each one before it reached production. Estimated savings: $8,200/month in support efficiency, from a server that took 4 days to build and test.
