---
title: Set Up Biome for Fast Linting and Formatting
slug: set-up-biome-for-fast-linting-and-formatting
description: >-
  Replace ESLint + Prettier with Biome — a single tool for linting, formatting,
  and import sorting that runs 25x faster. Configure for TypeScript, React,
  CI integration, and gradual migration from existing tools.
skills:
  - biome
  - github-actions
category: developer-experience
tags:
  - linting
  - formatting
  - biome
  - developer-experience
  - tooling
---

# Set Up Biome for Fast Linting and Formatting

Maya's project has ESLint (with 12 plugins), Prettier, and lint-staged. Running `eslint --fix` takes 45 seconds on her 800-file codebase. Editor feedback is sluggish. She wants Biome — one tool that replaces ESLint + Prettier, runs in Rust, and formats her entire codebase in under a second. The migration is gradual: she can enable rules incrementally without a big-bang rewrite.

## Step 1: Install and Initialize

```bash
npm install -D @biomejs/biome
npx biome init
```

```json
// biome.json — Generated config, customized
{
  "$schema": "https://biomejs.dev/schemas/2.0/schema.json",
  "organizeImports": {
    "enabled": true
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "indentWidth": 2,
    "lineWidth": 100
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "complexity": {
        "noExcessiveCognitiveComplexity": {
          "level": "warn",
          "options": { "maxAllowedComplexity": 15 }
        }
      },
      "correctness": {
        "noUnusedVariables": "error",
        "noUnusedImports": "error",
        "useExhaustiveDependencies": "warn"
      },
      "suspicious": {
        "noExplicitAny": "warn",
        "noConsoleLog": "warn"
      },
      "style": {
        "useConst": "error",
        "useTemplate": "error",
        "noNonNullAssertion": "warn"
      },
      "performance": {
        "noAccumulatingSpread": "error"
      }
    }
  },
  "javascript": {
    "formatter": {
      "quoteStyle": "double",
      "semicolons": "always",
      "trailingCommas": "all",
      "arrowParentheses": "always"
    }
  },
  "files": {
    "ignore": [
      "node_modules",
      "dist",
      ".next",
      "coverage",
      "*.gen.ts",
      "*.d.ts"
    ]
  }
}
```

## Step 2: Migrate from ESLint + Prettier

```bash
# Biome can migrate your existing config
npx biome migrate eslint --write
npx biome migrate prettier --write

# Check what Biome would change
npx biome check --write --unsafe .

# See diagnostics without fixing
npx biome check .

# Format only
npx biome format --write .
```

```json
// package.json — Replace old scripts
{
  "scripts": {
    "lint": "biome check .",
    "lint:fix": "biome check --write .",
    "format": "biome format --write .",
    "check": "biome check --write --unsafe ."
  }
}
```

```bash
# Remove old tools
npm uninstall eslint prettier eslint-config-prettier eslint-plugin-react \
  eslint-plugin-react-hooks eslint-plugin-import @typescript-eslint/eslint-plugin \
  @typescript-eslint/parser eslint-plugin-unused-imports

# Remove old config files
rm .eslintrc.* .prettierrc* .eslintignore .prettierignore
```

## Step 3: Git Hooks with lint-staged

```bash
npm install -D husky lint-staged
npx husky init
```

```json
// package.json
{
  "lint-staged": {
    "*.{ts,tsx,js,jsx,json,css,md}": [
      "biome check --write --no-errors-on-unmatched"
    ]
  }
}
```

```bash
# .husky/pre-commit
npx lint-staged
```

## Step 4: CI Integration

```yaml
# .github/workflows/lint.yml
name: Lint & Format
on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: biomejs/setup-biome@v2
      - run: biome ci .
```

## Step 5: Editor Setup

```json
// .vscode/settings.json
{
  "editor.defaultFormatter": "biomejs.biome",
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports.biome": "explicit",
    "quickfix.biome": "explicit"
  },
  "[typescript]": { "editor.defaultFormatter": "biomejs.biome" },
  "[typescriptreact]": { "editor.defaultFormatter": "biomejs.biome" },
  "[javascript]": { "editor.defaultFormatter": "biomejs.biome" },
  "[json]": { "editor.defaultFormatter": "biomejs.biome" }
}
```

```json
// .vscode/extensions.json
{
  "recommendations": ["biomejs.biome"]
}
```

## Summary

Maya's lint time dropped from 45 seconds to 0.8 seconds. One tool replaces ESLint (with all its plugins) and Prettier. Import sorting happens automatically on save. The migration took an afternoon — Biome's `migrate` command translated her existing ESLint and Prettier configs, and she incrementally tightened rules over a few PRs. The CI check runs in 2 seconds instead of 30. Editor feedback is instant. Her team doesn't argue about formatting anymore because Biome is opinionated and fast enough that nobody notices it running.
