---
title: "Automate Release Notes from Git History with AI"
slug: automate-release-notes
description: "Generate polished, user-facing release notes by analyzing git commits, PRs, and changelogs automatically."
skills: [changelog-generator, git-commit-pro]
category: productivity
tags: [release-notes, changelog, git, automation, developer-productivity]
---

# Automate Release Notes from Git History with AI

## The Problem

Release day arrives and nobody wrote the changelog. The PM asks "what shipped this week?" and the lead engineer spends 45 minutes scrolling through `git log`, trying to translate cryptic commit messages into something customers can understand. Half the changes get missed, the formatting is inconsistent, and by the time it's done, the actual release is delayed.

The commits themselves tell the story — but it's written in a language only the author understands. "fix: edge case in calc" could mean anything. "wip" appears 14 times. One commit message just says "stuff." Another developer writes three paragraphs for a one-line CSS change. The information is all there in the git history; it just needs to be extracted, categorized, and translated into something humans want to read. But doing that manually for 80+ commits every two weeks is soul-crushing work that nobody volunteers for.

## The Solution

Using the **changelog-generator** skill to extract and categorize changes from git history, and **git-commit-pro** to ensure future commits are structured for easy parsing, the agent reads commits between two tags, groups them by type (features, fixes, breaking changes), and outputs polished release notes — both a developer changelog and a user-facing version. The developer changelog goes into `CHANGELOG.md`; the user-facing version goes on the blog.

## Step-by-Step Walkthrough

### Step 1: Analyze Recent Changes

```text
Generate release notes for version 2.4.0. Compare the changes between tags v2.3.0 and HEAD on main.
```

### Step 2: Categorize Changes from Git History

The agent runs `git log v2.3.0..HEAD --oneline`, reads each commit and its associated PR, and groups everything into a structured changelog. It doesn't just match on commit prefixes — it analyzes the actual diff to understand what changed, which means even poorly-written commit messages get correctly categorized. A commit message that says "fix stuff" gets classified as a bug fix because the diff shows a corrected conditional in the report scheduler:

**v2.4.0 (2026-02-17)**

**New Features**
- Add bulk import for CSV files up to 50MB (#312)
- Support dark mode across all dashboard views (#298)
- Add webhook notifications for failed payments (#305)

**Bug Fixes**
- Fix timezone offset in scheduled reports (#315)
- Resolve memory leak in WebSocket connection handler (#308)
- Fix pagination breaking on filtered search results (#301)

**Performance**
- Reduce dashboard load time by 40% with query caching (#310)

**Internal**
- Upgrade Node.js from 20 to 22 (#303)
- Migrate CI pipeline from CircleCI to GitHub Actions (#307)

Every entry links to its PR number. The "Internal" section captures changes that matter to the engineering team but shouldn't appear in customer-facing notes. The distinction between "Performance" and "Bug Fixes" means customers can quickly scan for what's relevant to them.

### Step 3: Translate to User-Facing Language

The developer changelog is useful internally, but customers don't care about WebSocket connection handlers. The user-facing version strips the jargon and talks about outcomes:

```text
Now rewrite these as user-facing release notes for our blog. Our audience is non-technical small business owners who use our invoicing platform.
```

The rewrite speaks the customer's language:

**What's New in BillFlow 2.4.0**

**Import your data faster** — You can now upload CSV files up to 50MB to bulk-import customers, invoices, or products. No more adding them one by one.

**Dark mode is here** — Every screen in your dashboard now supports dark mode. Toggle it in Settings, then Appearance.

**Get notified about failed payments** — Set up webhook alerts so your team knows instantly when a customer payment fails. No more checking manually.

**Bug fixes** — We fixed an issue where scheduled reports showed the wrong timezone, and search results now paginate correctly when filters are applied.

**Faster dashboards** — Your main dashboard loads up to 40% faster thanks to improved caching.

Same changes, completely different framing. "Resolve memory leak in WebSocket connection handler" becomes invisible — customers don't need to know about it, and telling them would only cause concern. The Node.js upgrade and CI migration don't appear at all. The focus shifts from what was done technically to what changed for the user.

This dual output is the real value: engineers get the detailed changelog they need for debugging and tracking, customers get the friendly summary they'll actually read, and both are generated from the same source of truth. No more inconsistencies between what engineering says shipped and what the blog post announces.

### Step 4: Append to CHANGELOG.md

```text
Append this release to CHANGELOG.md in Keep a Changelog format.
```

The new version entry gets prepended to the existing `CHANGELOG.md`, maintaining consistent formatting with previous releases. The file stays in [Keep a Changelog](https://keepachangelog.com) format — `Added`, `Fixed`, `Changed`, `Deprecated`, `Removed`, `Security` sections — so tooling that parses it continues to work. Previous entries remain untouched.

This matters more than it sounds. A well-maintained CHANGELOG.md is often the first file enterprise customers check when evaluating a product. An inconsistent or incomplete changelog signals that the team doesn't take releases seriously. An automatically generated one is always complete and always formatted correctly.

### Step 5: Set Up Better Commits for Next Time

The quality of release notes depends directly on the quality of commit messages. The current git log is a mess, so fixing it at the source pays dividends on every future release:

```text
Our commit messages are messy. Set up a commit convention so future changelogs are easier to generate.
```

The agent configures Conventional Commits with a `.gitmessage` template that developers see every time they run `git commit`:

- `feat:` — New feature (triggers minor version bump)
- `fix:` — Bug fix (triggers patch version bump)
- `perf:` — Performance improvement
- `docs:` — Documentation only
- `chore:` — Maintenance, dependencies, CI
- `BREAKING CHANGE:` in the footer — triggers major version bump

The template shows up in the editor with examples and the allowed prefixes:

```
# <type>(<scope>): <description>
#
# Types: feat, fix, perf, docs, chore, refactor, test, style
# Scope: optional, e.g. dashboard, api, auth
#
# Examples:
#   feat(dashboard): add CSV bulk import up to 50MB
#   fix(reports): correct timezone offset in scheduled exports
#   perf(api): add query caching for dashboard endpoint
#
# Breaking changes: add "BREAKING CHANGE:" in the footer
```

With structured commits, the next release's changelog practically writes itself. The agent can map `feat:` to "New Features" and `fix:` to "Bug Fixes" with 100% accuracy instead of guessing from freeform messages. A commit like `feat(dashboard): add CSV bulk import up to 50MB` becomes a release note entry with no human intervention.

## Real-World Example

Dani, the engineering lead at a 12-person SaaS startup, releases every two weeks. Before this workflow, changelog day meant 2 hours of archaeology through 80+ commits written by 5 developers with wildly different styles. One developer writes novels in commit messages; another writes single words. The PM would ask for a summary and Dani would dread the question.

Dani asks the agent to generate release notes from `v3.11.0` to `HEAD`. It parses 83 commits, identifies 12 features, 9 bug fixes, and 1 breaking change. The breaking change gets flagged prominently: "API endpoint `/v1/tasks` renamed to `/v2/tasks`" — the kind of thing that's easy to miss buried in a git log but breaks every integration partner if it ships without notice. Two integration partners had already been burned by undocumented breaking changes; this time they get advance warning.

Both the customer-facing blog post and the developer changelog are ready in under 2 minutes. The blog post goes out with the release instead of three days later — or never, which was happening more often than Dani wanted to admit. The team also adopts Conventional Commits with the git-commit-pro skill, and each subsequent changelog gets more accurate. After three releases with structured commits, the agent stops guessing and starts mapping directly from prefixes. Changelog day goes from a 2-hour ordeal to a 5-minute review.
