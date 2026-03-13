---
title: Set Up GitHub Actions CI for a Monorepo
slug: set-up-github-actions-ci-for-monorepo
description: >-
  Build an efficient GitHub Actions CI pipeline for a monorepo — run jobs
  only for changed packages, cache dependencies aggressively, parallelize
  builds and tests, and deploy affected services automatically.
skills:
  - github-actions
  - turborepo
  - docker-compose
  - vitest
category: ci-cd
tags:
  - github-actions
  - ci-cd
  - monorepo
  - automation
  - devops
---

# Set Up GitHub Actions CI for a Monorepo

Pavel's monorepo has 3 apps and 5 packages. Every PR triggers a full build of everything — 15 minutes per CI run, even for a README change. He wants CI that detects which packages changed, runs only the relevant builds and tests in parallel, caches aggressively, and auto-deploys affected services when merging to main.

## Step 1: Detect Changed Packages

```yaml
# .github/workflows/ci.yml
name: CI
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  changes:
    runs-on: ubuntu-latest
    outputs:
      web: ${{ steps.filter.outputs.web }}
      api: ${{ steps.filter.outputs.api }}
      admin: ${{ steps.filter.outputs.admin }}
      packages: ${{ steps.filter.outputs.packages }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            web:
              - 'apps/web/**'
              - 'packages/ui/**'
              - 'packages/db/**'
              - 'packages/config-ts/**'
            api:
              - 'apps/api/**'
              - 'packages/db/**'
              - 'packages/config-ts/**'
            admin:
              - 'apps/admin/**'
              - 'packages/ui/**'
              - 'packages/db/**'
            packages:
              - 'packages/**'
```

## Step 2: Parallel Build and Test Jobs

```yaml
  # Shared setup
  install:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm
      - run: pnpm install --frozen-lockfile
      # Cache node_modules for downstream jobs
      - uses: actions/cache/save@v4
        with:
          path: |
            node_modules
            apps/*/node_modules
            packages/*/node_modules
          key: modules-${{ hashFiles('pnpm-lock.yaml') }}

  lint:
    needs: [install]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - uses: actions/cache/restore@v4
        with:
          path: |
            node_modules
            apps/*/node_modules
            packages/*/node_modules
          key: modules-${{ hashFiles('pnpm-lock.yaml') }}
      - run: pnpm turbo lint typecheck
        env:
          TURBO_TOKEN: ${{ secrets.TURBO_TOKEN }}
          TURBO_TEAM: ${{ secrets.TURBO_TEAM }}

  test-web:
    needs: [install, changes]
    if: needs.changes.outputs.web == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - uses: actions/cache/restore@v4
        with:
          path: |
            node_modules
            apps/*/node_modules
            packages/*/node_modules
          key: modules-${{ hashFiles('pnpm-lock.yaml') }}
      - run: pnpm turbo test --filter=@repo/web...
        env:
          TURBO_TOKEN: ${{ secrets.TURBO_TOKEN }}
          TURBO_TEAM: ${{ secrets.TURBO_TEAM }}

  test-api:
    needs: [install, changes]
    if: needs.changes.outputs.api == 'true'
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - uses: actions/cache/restore@v4
        with:
          path: |
            node_modules
            apps/*/node_modules
            packages/*/node_modules
          key: modules-${{ hashFiles('pnpm-lock.yaml') }}
      - run: pnpm turbo test --filter=@repo/api...
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/test
          REDIS_URL: redis://localhost:6379
          TURBO_TOKEN: ${{ secrets.TURBO_TOKEN }}
          TURBO_TEAM: ${{ secrets.TURBO_TEAM }}
```

## Step 3: Build and Deploy on Merge

```yaml
  build-web:
    needs: [lint, test-web]
    if: github.event_name == 'push' && needs.changes.outputs.web == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: pnpm }
      - run: pnpm install --frozen-lockfile
      - run: pnpm turbo build --filter=@repo/web...
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          working-directory: apps/web
          vercel-args: --prod

  deploy-api:
    needs: [lint, test-api]
    if: github.event_name == 'push' && needs.changes.outputs.api == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          file: apps/api/Dockerfile
          push: true
          tags: ghcr.io/${{ github.repository }}/api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

## Step 4: PR Status Checks

```yaml
  # Required status check that passes when all needed jobs succeed
  ci-ok:
    needs: [lint, test-web, test-api]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - name: Check all jobs
        run: |
          if [[ "${{ contains(needs.*.result, 'failure') }}" == "true" ]]; then
            echo "❌ Some jobs failed"
            exit 1
          fi
          echo "✅ All jobs passed (skipped jobs are OK)"
```

## Summary

Pavel's CI runs in 3 minutes instead of 15. Path filters detect which packages changed — a frontend-only PR skips API tests entirely. The `install` job caches `node_modules` for all downstream jobs. Turbo's remote cache means even the build step is often a cache hit. On merge to main, only changed services deploy. The `ci-ok` job provides a single required status check that handles skipped jobs correctly (a skipped test job doesn't block the PR). API tests spin up real PostgreSQL and Redis service containers for integration testing.
