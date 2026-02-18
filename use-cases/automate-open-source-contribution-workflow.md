---
title: "Automate Open Source Contribution Workflow with AI"
slug: automate-open-source-contribution-workflow
description: "Find good-first-issues, prepare PRs, and manage CLAs across open source projects using AI agents."
skills: [github, code-reviewer, coding-agent]
category: development
tags: [open-source, github, contributions, pull-requests, automation]
---

# Automate Open Source Contribution Workflow with AI

## The Problem

Dani's engineering team wants to contribute to the open source projects they depend on — fix that Prisma edge case they keep hitting, improve the Next.js middleware docs, close the React type inference bug that has been bothering them for months. But nobody has time to trawl through issue trackers, read contribution guides, figure out CLA requirements, and prepare properly formatted PRs for three different repos with three different conventions.

A senior developer might spend 3-4 hours just finding a suitable issue and understanding the contribution setup before writing a single line of code. The development environment for a project like Next.js is a monorepo with its own build system, custom test runner, and a changeset process that is not obvious from the README. Most contribution attempts stall not because the code is hard, but because the overhead of getting started is too high. The team has a Slack channel called `#upstream-fixes` with a dozen bookmarked issues that nobody has touched in months.

## The Solution

Using the **github** skill to search for issues and manage PRs, the **code-reviewer** to understand repository conventions, and the **coding-agent** to implement fixes, the agent handles the tedious parts — finding issues, reading CONTRIBUTING.md files, checking CLA requirements, locating the right files in an unfamiliar monorepo — so the developer can focus on writing the actual fix.

## Step-by-Step Walkthrough

### Step 1: Find Suitable Issues in Your Dependency Graph

Start by telling the agent which projects matter to the team:

```text
Search for good-first-issue and help-wanted labels in these repos: facebook/react, vercel/next.js, and prisma/prisma. Filter for issues opened in the last 30 days that haven't been assigned yet.
```

The key filter is "not yet assigned." Nothing is more frustrating than spending two hours on a fix only to discover someone else claimed the issue three days ago.

### Step 2: Review the Prioritized Results

The search queries GitHub's API, filters by labels and assignment status, and ranks by activity and estimated complexity:

| # | Issue | Labels | Age | Comments | Complexity |
|---|---|---|---|---|---|
| 1 | vercel/next.js #58234 — Fix middleware redirect loop with trailing slashes | good-first-issue, bug | 3 days | 2 | Low — isolated to one handler |
| 2 | prisma/prisma #21847 — Add TypeScript example for nested create with relations | help-wanted, docs | 5 days | 0 | Low — documentation addition |
| 3 | facebook/react #29182 — useReducer type inference breaks with discriminated unions | good-first-issue, type: bug | 12 days | 7 | Medium — TypeScript type changes |

Issue #1 is the sweet spot: recent, low complexity, clearly scoped, and only 2 comments (so it has not turned into a design debate). Issues with 10+ comments often mean the maintainers are still discussing the approach, and a PR submitted before consensus is reached will sit in limbo.

Issue #2 is the safest bet for a first-time contributor. Documentation PRs have the highest acceptance rate and help you learn the codebase without the pressure of a code change. They also build goodwill with maintainers, which makes your next code PR easier.

Issue #3 is more technically interesting but riskier — 7 comments suggest active discussion about the right fix, and TypeScript type changes in React's core require deep familiarity with the type system.

### Step 3: Analyze the Contribution Requirements

Dani picks the Next.js middleware issue. Before writing any code, she needs to understand what the project expects:

```text
I want to work on vercel/next.js #58234. Read their CONTRIBUTING.md, check for CLA requirements, and tell me what I need to do before submitting a PR.
```

This is where most first-time contributors lose an hour. Every major project has its own conventions — branch naming, test framework, commit message format, changelog requirements — and missing any one of them means a PR that sits in review limbo or gets closed with a "please follow our contribution guide" comment.

### Step 4: Review the Contribution Checklist

For vercel/next.js, the requirements are:

- **CLA:** Contributor License Agreement required — sign at `https://cla.vercel.com` before the PR can be merged. The CLA bot will block the PR until this is done, so sign it first.
- **Branch:** Fork and create branch from `canary`, not `main`. This catches many first-time contributors off guard.
- **Tests:** Must include an integration test in `test/integration/`
- **Linting:** Run `pnpm lint` before submitting — the CI check is strict and will fail on warnings
- **Changeset:** Run `pnpm changeset` to generate a changelog entry. Choose "patch" for bug fixes.
- **PR template:** Must reference the issue number and describe the fix

The relevant code is in `packages/next/src/server/web/spec-extension/response.ts`. The bug is in the `redirect()` function — it does not strip trailing slashes before checking the redirect target, causing an infinite loop when the incoming URL has a trailing slash and the redirect target does not. This is a 5-line fix, but finding it in a monorepo with 3,000+ files is the hard part.

### Step 5: Implement and Submit the PR

With the requirements clear and the bug located, Dani asks for the implementation:

```text
Create the fix for issue #58234. Write the code change and the integration test, then prepare the PR description following their template.
```

The fix adds a URL normalization step to the redirect comparison. Before checking whether the redirect target matches the current URL (which is what prevents infinite loops), trailing slashes are stripped from both sides. The change is small — about 5 lines in the redirect handler:

```typescript
// packages/next/src/server/web/spec-extension/response.ts
function normalizeUrl(url: string): string {
  return url.endsWith('/') ? url.slice(0, -1) : url
}

// In the redirect method, compare normalized URLs
if (normalizeUrl(destination) === normalizeUrl(request.url)) {
  throw new Error('Redirect loop detected')
}
```

The integration test covers three cases:

1. Redirect where the source URL has a trailing slash and the target does not — this was the original bug
2. Redirect where neither URL has a trailing slash — should work exactly as before (no regression)
3. The infinite loop scenario from the original issue — the test that prevents this bug from coming back

The PR description follows the Next.js template: references issue #58234, describes the root cause (URL comparison without slash normalization), explains the fix, links to the test, and notes that the changeset was generated with `pnpm changeset`. The git commands to push to Dani's fork and open the PR are ready to copy:

```bash
git remote add fork git@github.com:dani/next.js.git
git push fork fix/middleware-trailing-slash-redirect
gh pr create --repo vercel/next.js --base canary \
  --title "fix: normalize trailing slashes in middleware redirect" \
  --body-file pr-description.md
```

### Step 6: Comment on the Issue Before Pushing

One last step that most first-time contributors skip: leave a comment on the issue before opening the PR. "I'd like to work on this. The bug is in the redirect handler's URL comparison — I have a fix and test ready." This serves three purposes:

- It prevents duplicate effort — someone else might be working on the same issue
- It signals to maintainers that the issue is actively being worked on, so they do not close it as stale
- It gives maintainers a chance to share context or redirect your approach before you invest more time

Most maintainers appreciate this etiquette and will assign the issue to you within a few hours.

## Real-World Example

Dani picks the Prisma edge case her team has been working around for weeks — a JSON field serialization bug in `prisma/prisma` issue #21650. The team has a 15-line workaround in their codebase that runs a `JSON.parse(JSON.stringify(...))` round-trip before every JSON write to avoid a serialization error with nested objects containing special characters. The workaround works, but it is ugly, it adds latency, and every new developer asks "why is this here?"

She asks the agent to analyze the issue and the repo's contribution setup. The Prisma monorepo has 20+ packages, each with its own directory structure and test setup. Without guidance, finding the right file to edit would mean grepping through hundreds of source files. The agent reads CONTRIBUTING.md, identifies the CLA bot link (Prisma uses a bot that comments on the PR), locates the relevant package (`packages/client/src/runtime/core/jsonProtocol/serialize.ts`), and finds the existing test patterns in `packages/client/tests/functional/json-fields/`.

Dani signs the CLA — a 30-second process through Prisma's GitHub bot — then asks the agent to implement the fix following the repo's testing conventions. The fix goes into the serialization module: a 12-line change to handle nested JSON objects with special characters by properly escaping them before serialization instead of letting them break the JSON protocol wire format. The test follows the exact pattern used by adjacent test files: same `_matrix.ts` setup for the test matrix, same `prisma/_schema.prisma` for the test schema, same assertion style.

She reviews the code to make sure the fix makes sense, pushes to her fork, and opens the PR with the generated description. Total time from issue to PR: 45 minutes instead of the half-day it would have taken to navigate the monorepo, find the right test patterns, figure out the changeset process, and read enough of the serialization code to locate the bug.

The PR gets reviewed within a week. The Prisma maintainer suggests one minor change — extracting the escape logic into a helper function for clarity — which Dani makes in 5 minutes. The PR merges, and Dani's team removes their 15-line workaround in the next Prisma upgrade. One less piece of tech debt, one fewer "why is this here?" question from new hires, and one more contribution to the open source projects the team relies on every day.
