---
title: "Build an Automated Code Review Checklist from Team Standards with AI"
slug: build-automated-code-review-checklist
description: "Use AI to extract coding standards from team docs, generate PR review checklists, and enforce them automatically on every pull request."
skills: [code-reviewer, doc-parser, github]
category: development
tags: [code-review, standards, automation, pull-request, quality]
---

# Build an Automated Code Review Checklist from Team Standards with AI

## The Problem

A backend team of eight has coding standards documented across a Notion page, a CONTRIBUTING.md file, an old wiki article, and tribal knowledge in senior developers' heads. Code reviews are inconsistent — one reviewer catches naming convention violations, another focuses on error handling, a third waves everything through because they're in a rush.

New hires have no idea what "our standards" actually look like because they're scattered across four places and half-contradictory. One document says "use console.log for debugging," another says "never use console.log, use the Logger class." Which one is right? Depends on who you ask. PRs get approved with logged passwords, missing input validation, and inconsistent error codes — because no single reviewer remembers every rule. Two weeks ago, a PR that logs the entire user object (including email and hashed password) passed review and made it to production. The standards exist on paper, just not in practice.

## The Solution

Using the **doc-parser**, **code-reviewer**, and **github** skills, the workflow extracts every coding rule from scattered documentation, deduplicates and resolves contradictions, produces a unified checklist, and enforces it automatically on every PR with inline comments on violations. Reviewers stop being human linters and focus on what humans are actually good at: architecture decisions, business logic correctness, and code design.

## Step-by-Step Walkthrough

### Step 1: Extract Standards from Scattered Sources

Point the agent at every document that contains team rules:

```text
Read these files containing our team coding standards: /docs/CONTRIBUTING.md, /docs/notion-export-coding-guidelines.md, /docs/wiki-backend-standards.html. Extract every specific rule — naming conventions, error handling patterns, logging requirements, security practices, API response formats. Deduplicate and flag any contradictions.
```

The parser processes all three sources and extracts 67 rules total. After deduplication — many rules appear in multiple documents with slightly different wording — 48 unique rules remain:

**Naming (8 rules):**
- Use camelCase for variables and functions
- Use PascalCase for classes and interfaces
- Prefix boolean variables with `is`/`has`/`should`
- Database column names use snake_case

**Error Handling (7 rules):**
- Always use custom error classes extending `AppError`
- Never catch and swallow errors silently
- Log the original error before re-throwing
- Return consistent error response: `{ error: { code, message, details } }`

**Security (6 rules):**
- Never log sensitive fields (`password`, `token`, `ssn`, `credit_card`)
- Validate all input at the controller layer
- Use parameterized queries, never string concatenation for SQL

And 27 more rules across logging, testing, API design, and documentation.

**Contradictions found (2):**
1. CONTRIBUTING.md says "use console.log for debugging" -- Wiki says "never use console.log, use the Logger class"
2. Notion says "return 400 for all client errors" -- CONTRIBUTING.md says "use specific codes: 400, 401, 403, 404, 422"

Those contradictions explain why reviews are inconsistent — the developers are literally following different source documents, and both sides are "right" according to their reference.

### Step 2: Resolve Contradictions and Finalize

```text
For the two contradictions, use the most recent document's version (Notion was last updated in December 2024, CONTRIBUTING.md in August 2024). Produce a final checklist document in markdown with rules grouped by category, each with a clear pass/fail description.
```

The unified `REVIEW_CHECKLIST.md` resolves both contradictions (Logger class wins because the wiki is newer, specific HTTP codes win because the Notion doc is newer) and groups every rule by category with checkboxes:

```markdown
# Code Review Checklist

## Naming Conventions
- [ ] Variables and functions use camelCase
- [ ] Classes and interfaces use PascalCase
- [ ] Boolean variables prefixed with is/has/should
- [ ] Database columns use snake_case

## Error Handling
- [ ] Custom error classes extend AppError
- [ ] No silent catch blocks (every catch logs or re-throws)
- [ ] Consistent error response format: { error: { code, message, details } }

## Security
- [ ] No sensitive fields in log statements (password, token, ssn, credit_card)
- [ ] All controller inputs validated with schema
- [ ] SQL uses parameterized queries only
```

One source of truth, 48 rules, zero contradictions. The checklist lives in the repo so it's versioned alongside the code — not in a Notion page that drifts out of sync.

### Step 3: Build the PR Review Bot

```text
Convert the checklist into a GitHub Actions workflow that runs on every PR. For each changed file, check the applicable rules and post inline comments on violations. Use the code-reviewer skill's analysis — don't just pattern match, understand the code context.
```

The agent creates `.github/workflows/review-checklist.yml` and a review configuration that maps rules to code patterns. The bot understands context — it won't flag `console.log` in a test helper or a build script, and it knows that a `catch` block that re-throws with additional context isn't "swallowing" the error. A regex-based linter would flag both of those as violations; a context-aware reviewer doesn't.

The workflow runs only on changed files, so it's fast even on large PRs — a 3-file PR gets reviewed in under 30 seconds. Comments are posted inline on the specific line that violates a rule, not as a wall of text at the bottom of the PR. Each comment includes the rule that was violated and a brief explanation of why it matters:

> **Security: No sensitive fields in log statements**
> `logger.info(user)` logs the entire user object, which includes `email` and `hashedPassword`. Use `logger.info({ id: user.id, role: user.role })` to log only non-sensitive fields.

The specificity matters. "Don't log sensitive data" is a rule; showing the developer which line, which object, and which fields are the problem is actionable feedback.

### Step 4: Calibrate Against Recent PRs

Before rolling out to the team, test against history to make sure the signal is clean:

```text
Run the automated checklist against our last 10 merged PRs. Show which rules each PR would have violated. This helps us calibrate — if the tool flags too many false positives, we'll adjust.
```

**Retroactive analysis — last 10 PRs:**

| PR | Violations |
|----|------------|
| #287 (Add user preferences endpoint) | Security: `req.body` used without validation schema (line 42). Error handling: catch block swallows error (line 78) |
| #285 (Fix payment retry logic) | Security: logs contain user email at line 31 (`logger.info(user)` logs the entire user object) |
| #283 (Refactor notification service) | Clean — no violations |
| #281 (Update dashboard queries) | Clean — no violations |
| #279 (Add team invite feature) | Security: missing input validation on invite endpoint. Naming: boolean `active` should be `isActive` |
| #277 (Fix CSV export) | Error handling: generic catch block returns 500 without logging |
| #275 (Update billing webhooks) | Clean — no violations |
| #273 (Add audit logging) | Naming: inconsistent casing in 2 variables |
| #271 (Refactor auth middleware) | Clean — no violations |
| #269 (Add rate limiting) | Clean — no violations |

**Summary:** 10 PRs, 14 violations found, 0 false positives. Most common violation: missing input validation (5 cases). The security issue in #285 — logging the entire user object — is the exact kind of bug that caused the incident two weeks ago.

Zero false positives is the number that matters most. If the bot cried wolf on every PR, the team would ignore it within a week and disable the workflow within a month.

### Step 5: Roll Out to the Team

```text
Write a brief team announcement explaining the new automated review checklist. Include a link to the REVIEW_CHECKLIST.md, explain how the bot works, and note that it's advisory for the first two weeks (comments only, no blocking).
```

The two-week advisory period is important — it lets the team see what the bot catches and builds trust in its judgment before giving it any authority. Comments only, no merge blocking. Developers can read the comments, fix the issues if they agree, and ignore them if they don't. After two weeks of clean signal (no false positives, consistent catches), the team votes to make it mandatory.

The announcement also links to the `REVIEW_CHECKLIST.md` — for the first time, every developer on the team can read every standard in one place. New hires no longer have to piece together tribal knowledge from three outdated documents.

## Real-World Example

Hiro is a tech lead at a 25-person B2B startup with eight backend engineers. Reviews are a lottery — some PRs sail through, others get nitpicked on formatting, depending on which senior dev reviews them. A new hire's PR gets 47 comments about naming conventions; the next week, a senior engineer's PR with a security issue gets approved in 10 minutes. The inconsistency is demoralizing.

Hiro asks the agent to consolidate standards from the three outdated docs. The agent finds 48 rules, resolves two contradictions, and produces a clean checklist. A retroactive scan of the last 10 PRs finds 14 real violations — including one PR that logs user emails in plaintext, which passed review and reached production two weeks ago.

The team rolls out the automated review bot in advisory mode. Within a month, code review time drops 30% because reviewers no longer manually check formatting, naming conventions, and security basics — the bot handles the mechanical checks consistently every time. Humans focus on architecture and logic, the things they're actually good at. New hires ramp up faster because the bot teaches them the standards in real-time, on their own code. Standards that existed on paper now exist in practice.
