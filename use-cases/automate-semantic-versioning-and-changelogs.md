---
title: "Automate Semantic Versioning and Changelogs Across Your Repos"
slug: automate-semantic-versioning-and-changelogs
description: "Set up conventional commits, automated version bumping, and changelog generation so releases are consistent and effortless."
skills: [git-commit-pro, changelog-generator, cicd-pipeline]
category: productivity
tags: [versioning, changelog, semver, release-management, conventional-commits]
---

# Automate Semantic Versioning and Changelogs Across Your Repos

## The Problem

A team maintains 8 packages in a monorepo. Version numbers are bumped manually — sometimes the developer forgets, sometimes they bump a patch when it should be a minor. Changelogs are written by hand the night before a release, usually missing half the changes. Three times last quarter, a breaking change shipped as a patch version, breaking downstream consumers who trusted the version number.

Nobody trusts the version numbers anymore. Downstream teams pin exact versions instead of using semver ranges, which means they fall months behind on updates — including security patches. Customers have stopped reading changelogs because they're incomplete. The version system — the one mechanism that's supposed to communicate what changed and whether it's safe to upgrade — has become meaningless noise. When a consumer sees `2.3.1 -> 2.3.2`, they should be able to upgrade with confidence. Instead, they've learned that any bump might break them.

## The Solution

Using **git-commit-pro** to enforce conventional commits, **changelog-generator** to produce accurate changelogs from commit history, and **cicd-pipeline** to automate version bumping and publishing on merge to main, the entire release pipeline becomes deterministic: the commit message determines the version bump, the version bump determines the changelog, and the changelog ships automatically. No human judgment, no forgotten steps, no incorrect bumps.

## Step-by-Step Walkthrough

### Step 1: Audit the Damage

Before fixing the process, quantify the problem. Vague statements like "our versioning is inconsistent" don't drive action. Concrete numbers like "3 breaking changes shipped as patches" do:

```text
Analyze the last 200 commits in our monorepo. Categorize them by what they
actually did: bug fixes, new features, breaking changes, refactors, docs,
chores. Show me what the version history should have looked like if we had
used semver correctly. How many incorrect version bumps did we ship?
```

The audit of 200 commits reveals the breakdown:

| Category | Count |
|---|---|
| Bug fixes | 67 |
| Features | 41 |
| Breaking changes | 12 |
| Refactors | 48 |
| Docs updates | 19 |
| Chores | 13 |

And 8 version bumps that were wrong — each one a broken promise to downstream consumers:

- **3 breaking changes shipped as patches** — consumers running `npm update` pulled in breaking changes thinking it was safe. Two of these caused production outages for downstream teams.
- **2 features shipped as patches** — consumers on automated minor-bump schedules missed new capabilities because they weren't expecting them in a patch
- **3 patches that should have been chores** — no-op version bumps (docs changes, CI tweaks) that polluted the release history and triggered unnecessary downstream updates

A "what versions should have been" table shows the divergence. The `billing` package is 3 major versions behind where it should be — three separate breaking changes were hidden in patch releases. Consumers who trusted the version number got burned three times.

### Step 2: Enforce Conventional Commits

```text
Configure commitlint and husky for our monorepo so every commit must follow
the conventional commits spec. Our scopes should match our package names:
api, web, shared, cli, docs, auth, billing, notifications. Add a commit
message template that developers see when they run git commit. Include
the BREAKING CHANGE footer format.
```

The enforcement setup includes:

- **`.commitlintrc.js`** — validates commits against the conventional format with the 8 allowed scopes. Invalid scopes get rejected with a list of valid options.
- **Husky hooks** — `pre-commit` and `commit-msg` hooks that reject invalid messages before they enter the history. The rejection happens instantly and locally, not 5 minutes later in CI.
- **`.gitmessage` template** — shows developers the correct format with examples every time they run `git commit`, so nobody has to memorize the spec
- **`.vscode/settings.json`** — displays the template in VS Code's source control panel for developers who commit from the IDE

A commit like `fixed stuff` or `updates` now gets rejected immediately with a helpful error message showing the expected format: `fix(billing): correct proration calculation for annual plans`. Within a week of enforcement, 100% of commits follow the format — not because developers memorized it, but because the tooling won't let them do anything else. The initial resistance ("this is annoying") fades once developers see the first automatically generated changelog.

### Step 3: Generate Accurate Changelogs

```text
Generate a CHANGELOG.md for each package based on the last 6 months of
commits. Group entries by version, with sections for Features, Bug Fixes,
Breaking Changes, and Performance Improvements. Link each entry to its
commit hash and PR number. For breaking changes, include a migration guide
section explaining what consumers need to update.
```

Eight CHANGELOG.md files get generated, one per package. Each has properly grouped entries with commit links and PR references. The billing package changelog is the most revealing — 3 breaking changes that were previously invisible now have clear "Before/After" code examples showing exactly what consumers need to update:

```markdown
## Breaking Changes

### `calculateProration()` parameter order changed

**Before:**
calculateProration(amount, startDate, endDate)

**After:**
calculateProration({ amount, startDate, endDate, plan })

Migration: Update all call sites to use the options object.
Affected versions: 2.1.0+
```

For the first time, downstream teams can actually see what broke and how to fix it. The migration guides transform breaking changes from "figure out what happened" to "follow these steps." Three downstream teams update their integration within a day of receiving the changelog — previously these updates took weeks because nobody knew what had changed.

### Step 4: Automate the Release Pipeline

```text
Create a GitHub Actions release workflow that triggers on merge to main.
It should determine which packages changed, calculate the correct semver
bump from conventional commits, update package.json versions, generate
changelogs, create git tags, publish to npm, create GitHub Releases,
and post to our #releases Slack channel. Handle multiple packages
changing in one PR independently.
```

The workflow has four jobs that run in sequence:

1. **detect-changes** — identifies which packages were affected by the merged commits using file path analysis. A commit touching `packages/api/src/` only bumps the `api` package.
2. **bump-versions** — runs `standard-version` per package, calculating the correct increment from commit prefixes (`feat:` = minor, `fix:` = patch, `BREAKING CHANGE` footer = major). No human decides the version number.
3. **publish** — pushes to npm with provenance attestation, so consumers can verify the package came from this CI pipeline
4. **notify** — posts a formatted Slack message to `#releases` listing all released packages with their new versions and changelog excerpts

Each package gets its own independent version bump. A single PR that fixes a bug in `api` and adds a feature to `web` produces a patch bump for `api` and a minor bump for `web`. No manual coordination, no spreadsheet tracking which packages need which bump.

### Step 5: Handle the Dependency Cascade

The monorepo has internal dependencies: `api`, `web`, `cli`, and `auth` all depend on `shared`. A breaking change in `shared` needs to ripple through correctly:

```text
When the shared package gets a breaking change, all packages that depend on
it need a version bump too. Set up automatic dependency updates so the
release workflow handles this cascade in the right order.
```

A dependency graph resolver gets added to the release workflow. It topologically sorts packages by their internal dependencies, bumps them in order, and cascades version updates. When `shared` gets a breaking change to 3.0.0:

1. `shared` bumps to 3.0.0, published first
2. `api`, `web`, `cli`, and `auth` update their `shared` dependency to `^3.0.0`
3. Each gets at least a patch bump for the dependency update
4. All 5 packages are released in the correct order

npm never has a window where dependency resolution fails — every published version's dependencies are already available. The cascade runs automatically; nobody has to think about release ordering.

## Real-World Example

An engineering manager at a 35-person company runs the monorepo with 8 npm packages. Customers have complained that version numbers are unreliable, changelogs are incomplete, and breaking changes appear in patch releases. One downstream team pinned every dependency to an exact version out of distrust, which means they're 4 months behind on security patches — including one critical CVE that was fixed in a patch release they never pulled.

The commit audit reveals 8 incorrect version bumps in 6 months — including 3 breaking changes shipped as patches. Conventional commits get enforced, and within a week every commit follows the format. Auto-generated changelogs are accurate and complete for the first time; customer support stops fielding "what changed?" tickets.

Over the next quarter, the release workflow ships 47 correct version bumps with zero manual intervention. Not a single incorrect bump. Downstream teams start trusting semver again and switch back to caret ranges for dependencies, reducing their integration lag from 3 weeks to 2 days. The team that was 4 months behind catches up in a single afternoon. The version numbers mean something again.
