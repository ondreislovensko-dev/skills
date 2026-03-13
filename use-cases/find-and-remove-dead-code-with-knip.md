---
title: Find and Remove Dead Code with Knip
slug: find-and-remove-dead-code-with-knip
description: >-
  Use Knip to find unused files, dependencies, exports, and types in your
  TypeScript project — clean up dead code, reduce bundle size, and keep
  your codebase maintainable.
skills:
  - knip
  - github-actions
  - biome
category: developer-experience
tags:
  - dead-code
  - cleanup
  - tooling
  - typescript
  - dependencies
---

# Find and Remove Dead Code with Knip

Hugo's 3-year-old TypeScript project has 800 files but only 500 are actually used. `package.json` has 120 dependencies — at least 30 are unused. Exported functions sit unreferenced, types exist for deleted features, and entire utility files are imported nowhere. Manual cleanup is impossible at this scale. Knip statically analyzes the project and reports exactly what's unused: files, dependencies, exports, types, and enum members.

## Step 1: Install and Run

```bash
npm install -D knip
npx knip
```

```
# Output example:
Unused files (23)
  src/utils/deprecated-helper.ts
  src/components/OldDashboard.tsx
  src/lib/legacy-api-client.ts
  ...

Unused dependencies (7)
  moment
  lodash
  classnames
  ...

Unused devDependencies (4)
  @types/express
  jest
  ts-jest
  ...

Unused exports (45)
  src/lib/utils.ts: formatCurrency, debounce, throttle
  src/types/api.ts: LegacyUser, OldResponse
  ...

Unused types (12)
  src/types/index.ts: DeprecatedConfig, V1ApiResponse
  ...
```

## Step 2: Configuration

```json
// knip.json
{
  "$schema": "https://unpkg.com/knip@latest/schema.json",
  "entry": [
    "src/index.ts",
    "src/app/**/*.{ts,tsx}",
    "src/pages/**/*.{ts,tsx}"
  ],
  "project": ["src/**/*.{ts,tsx}"],
  "ignore": [
    "src/generated/**",
    "**/*.test.{ts,tsx}",
    "**/*.stories.{ts,tsx}"
  ],
  "ignoreDependencies": [
    "autoprefixer",
    "@types/node"
  ],
  "ignoreBinaries": ["docker"],
  "paths": {
    "@/*": ["src/*"]
  }
}
```

```json
// package.json
{
  "scripts": {
    "knip": "knip",
    "knip:fix": "knip --fix",
    "knip:production": "knip --production"
  }
}
```

## Step 3: Auto-Fix Safe Issues

```bash
# Remove unused exports (safe — if they're unused, nothing breaks)
npx knip --fix --allow-remove-files

# Preview what would be removed
npx knip --fix --dry-run

# Only check production code (skip test/story dependencies)
npx knip --production
```

## Step 4: Monorepo Configuration

```json
// knip.json for monorepo
{
  "workspaces": {
    "apps/web": {
      "entry": ["src/app/layout.tsx", "src/app/**/page.tsx"],
      "project": ["src/**/*.{ts,tsx}"]
    },
    "apps/api": {
      "entry": ["src/index.ts"],
      "project": ["src/**/*.ts"]
    },
    "packages/ui": {
      "entry": ["src/index.ts"],
      "project": ["src/**/*.{ts,tsx}"]
    },
    "packages/db": {
      "entry": ["src/index.ts", "src/schema.ts"],
      "project": ["src/**/*.ts"]
    }
  }
}
```

## Step 5: CI Integration

```yaml
# .github/workflows/lint.yml
name: Code Quality
on: [pull_request]

jobs:
  knip:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm }
      - run: npm ci
      - name: Check for unused code
        run: npx knip --no-exit-code --reporter json > knip-report.json
      - name: Comment on PR if issues found
        if: always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = JSON.parse(fs.readFileSync('knip-report.json', 'utf8'));
            const issues = report.files?.length + report.dependencies?.length + report.exports?.length;
            if (issues > 0) {
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                body: `⚠️ **Knip found unused code:**\n- ${report.files?.length || 0} unused files\n- ${report.dependencies?.length || 0} unused dependencies\n- ${report.exports?.length || 0} unused exports\n\nRun \`npx knip\` locally for details.`
              });
            }
```

## Step 6: Incremental Cleanup Strategy

```bash
# Week 1: Remove unused dependencies (biggest impact, safest)
npx knip --dependencies
npm uninstall moment lodash classnames  # etc.

# Week 2: Remove unused files
npx knip --files
# Review each file, then delete or move to archive

# Week 3: Remove unused exports
npx knip --exports
# Clean up each module's public API

# Ongoing: Run in CI to prevent new dead code
```

## Summary

Hugo removed 23 unused files, 7 unused dependencies (saving 12MB from node_modules), and 45 unused exports in an afternoon. Bundle size dropped 18% just from removing dead code paths that the bundler couldn't tree-shake (because they were still exported). Knip's CI integration catches new dead code before it merges — if someone removes the last usage of a function but doesn't delete the function itself, the PR gets flagged. The project went from 800 files to 777, and every remaining file is actually used. Running `npx knip` weekly keeps the codebase clean as it evolves.
