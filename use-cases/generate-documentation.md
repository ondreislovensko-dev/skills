---
title: "Automate Documentation Generation and Slash Onboarding Time"
slug: generate-documentation
description: "Generate comprehensive README files, API documentation, and developer guides by analyzing codebases to accelerate team onboarding."
skills: [markdown-writer, code-documenter, github]
category: development
tags: [documentation, readme, api-docs, onboarding, automation]
---

# Automate Documentation Generation and Slash Onboarding Time

## The Problem

Marcus, engineering lead at a 28-person fintech startup, watches new developers struggle for weeks to understand their codebase. 43 microservices, 12 different API patterns, zero comprehensive documentation. The README files are either empty or hopelessly outdated. New hires spend their first 3 weeks asking the same questions: "How do I run this locally?" "What does this endpoint expect?" "Who owns the auth service?"

The onboarding crisis is expensive. Average time to first meaningful contribution: 18 days. Senior engineers spend 4.5 hours weekly answering documentation questions instead of building features. With 8 planned hires this year, poor documentation will cost an estimated $376,000 in delayed productivity.

Code knowledge lives entirely in developers' heads. When Sarah (auth service owner) took vacation, the team spent 6 hours debugging an OAuth integration because no one understood the configuration flow. Critical deployment procedures exist only as Slack threads. API consumers guess at request formats, causing 23% more support tickets than necessary.

## The Solution

Combine **markdown-writer** for structured documentation, **code-documenter** for API analysis, and **github** for repository integration. The approach: analyze codebase structure, extract API definitions, audit existing docs, and generate comprehensive, maintainable documentation across all 43 services.

## Step-by-Step Walkthrough

### Step 1: Codebase Analysis and Documentation Audit

```text
Analyze our entire codebase across 43 services. Generate a comprehensive README for each service and a master architecture guide.
```

The analysis catalogs every service, its stack, endpoint count, and documentation status:

| Service | Stack | Endpoints | Doc Status |
|---|---|---|---|
| Authentication | Node.js/Express | 23 | Empty README |
| Payment Processing | Python/FastAPI | 31 | Outdated setup instructions |
| User Management | Go/Gin | 18 | Empty README |
| Notification Engine | Node.js | 12 | Empty README |
| (39 more services) | various | various | mostly undocumented |

The gap analysis is sobering:
- **31 of 43 services** (72%) have empty READMEs
- **41 of 43** (95%) have no API documentation
- **43 of 43** (100%) have no deployment guides
- Zero architecture overviews exist anywhere

Priority queue: start with auth (most dependencies), payment (regulatory requirements), then user management (core service).

### Step 2: API Documentation Extraction

```text
Extract all API endpoints, analyze request/response schemas, and generate OpenAPI documentation with examples.
```

Endpoint extraction works by reading route definitions, type annotations, and middleware chains to produce complete API documentation with working examples:

**Authentication Service (23 endpoints):**

```
POST /auth/login
  Request:  { email: string, password: string, mfa_code?: string }
  Response: { token: string, refresh: string, expires: number }

GET /auth/profile
  Headers:  Authorization: Bearer {token}
  Response: { id: string, email: string, roles: string[], created: date }
```

**Payment Processing Service (31 endpoints):**

```
POST /payments/charge    -- Stripe integration, idempotency key handling
GET  /payments/history   -- Paginated, filterable by user/date
POST /payments/refund    -- Admin-only, requires approval workflow
```

Every endpoint gets a working `curl` example, request/response schemas with types, and error code documentation. Schema validation confirms 94% of types were inferred accurately from the code -- the remaining 6% are edge cases that need manual review (mostly union types and overloaded endpoints).

### Step 3: Generate Consistent README Files

```text
Create detailed README files for each service including setup, configuration, testing, and deployment instructions.
```

Each service gets a README following a consistent template. Here's what the auth service README looks like:

```markdown
# Authentication Service
High-performance JWT-based authentication with MFA support.

## Quick Start
npm install
cp .env.example .env  # Configure your secrets
docker-compose up postgres redis
npm run dev  # Starts on port 3001
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `JWT_SECRET` | Yes | -- | Token signing secret |
| `MFA_ISSUER` | No | CompanyAuth | TOTP issuer name |
| `REDIS_URL` | Yes | `redis://localhost:6379` | Session store |

```markdown
## Testing
npm test                  # Unit tests
npm run test:integration  # Integration tests with DB
npm run test:load         # Load testing (100 req/s)

## Deployment
Deployed via GitHub Actions on merge to main.
See full API reference at ./API.md
```

The same template applies to all 43 services -- consistent structure, auto-detected dependencies, working commands verified against the actual codebase. A developer who reads one service's README knows exactly where to look in any other.

### Step 4: Master Architecture Documentation

```text
Create a system-wide architecture guide showing service relationships, data flows, and integration patterns.
```

The architecture guide ties everything together into a single document that answers the questions no individual README can:

- **Service directory** -- quick reference: what each service does, who owns it, which database it uses
- **Getting started guide** -- clone, configure, and run the entire 43-service stack in 10 minutes using Docker Compose
- **Data flow diagrams** -- request routing through auth, user, and payment pipelines
- **Integration patterns** -- JWT propagation between services, event sourcing, circuit breaker configuration
- **Troubleshooting guide** -- common issues and solutions mined from 180 resolved support tickets

The integration patterns section is particularly valuable. It documents how services authenticate with each other (JWT propagation vs. service accounts), which services use shared databases vs. service-owned databases, and where circuit breakers and retry logic are configured. These cross-cutting concerns lived entirely in tribal knowledge before.

### Step 5: Automated Documentation Maintenance

```text
Set up GitHub Actions to automatically update documentation when code changes, and validate examples still work.
```

Four GitHub Actions workflows prevent the documentation from going stale:

| Workflow | Trigger | What It Does |
|---|---|---|
| `docs-update.yml` | Code push | Regenerate API docs from route changes |
| `example-validation.yml` | Weekly | Test all curl examples in docs |
| `readme-sync.yml` | Service addition | Update master architecture overview |
| `broken-link-checker.yml` | Weekly | Find dead internal links, create issues |

The critical one is `docs-update.yml` -- it runs on every push, compares the API endpoints in code against the documented endpoints, and opens a PR if anything drifted. The same documentation drift problem that plagues manual docs is now caught automatically before merge.

## Real-World Example

The CTO of a 40-person SaaS company inherited 67 microservices with documentation scattered across wikis, Notion pages, and random README files. New engineers took 4 weeks to make their first contribution. Senior developers spent 30% of their time answering "How does X work?" questions.

On Thursday, code-documenter analyzed the entire codebase and discovered 847 API endpoints across all services. Many had undocumented features; some services had zero external documentation. Comprehensive API docs were generated with working examples for every endpoint.

On Friday, markdown-writer created consistent README files for all services -- installation instructions that actually worked, configuration tables, testing commands, and deployment guides. The architecture overview showed how everything connected.

On Monday, new hire Elena started. Using the documentation, she had the entire development environment running in 47 minutes (previous record: 3 days). By day 3, she'd shipped her first feature. Time to first contribution: 72% reduction.

Results after 2 months: onboarding time dropped from 4 weeks to 5 days. Senior developer "documentation support" hours dropped 85%. Support tickets related to integration confusion decreased 67%. The team estimated they reclaimed 2.3 full-time-equivalent hours weekly for actual development work -- hours that had been quietly disappearing into "Can you show me how this service works?" conversations.
