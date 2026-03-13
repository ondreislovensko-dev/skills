---
title: Build a Turborepo Monorepo for a Full-Stack Team
slug: build-turborepo-monorepo-for-fullstack-team
description: >-
  Set up a Turborepo monorepo with shared packages, parallel builds, remote
  caching, and CI pipelines — manage a Next.js app, API server, shared UI
  library, and config packages in one repository.
skills:
  - turborepo
  - github-actions
  - biome
  - vitest
category: developer-experience
tags:
  - monorepo
  - turborepo
  - typescript
  - ci-cd
  - tooling
---

# Build a Turborepo Monorepo for a Full-Stack Team

Zara's team maintains 4 repos: a Next.js frontend, an Express API, a shared UI component library, and a shared TypeScript config package. Changes to the UI library require publishing to npm, then updating 2 consumer repos, then deploying both. A CSS change takes 3 PRs. She wants one repo where shared code is shared directly, builds run in parallel, and CI only rebuilds what changed.

## Step 1: Repository Structure

```bash
npx create-turbo@latest my-monorepo
cd my-monorepo
```

```
my-monorepo/
├── apps/
│   ├── web/              # Next.js frontend
│   │   ├── package.json  # name: "@repo/web"
│   │   └── ...
│   └── api/              # Express API server
│       ├── package.json  # name: "@repo/api"
│       └── ...
├── packages/
│   ├── ui/               # Shared React components
│   │   ├── package.json  # name: "@repo/ui"
│   │   └── ...
│   ├── db/               # Shared database layer (Drizzle)
│   │   ├── package.json  # name: "@repo/db"
│   │   └── ...
│   ├── config-ts/        # Shared TypeScript config
│   │   ├── package.json  # name: "@repo/config-ts"
│   │   └── base.json
│   └── config-biome/     # Shared Biome config
│       ├── package.json  # name: "@repo/config-biome"
│       └── biome.json
├── turbo.json
├── package.json
└── pnpm-workspace.yaml
```

```yaml
# pnpm-workspace.yaml
packages:
  - "apps/*"
  - "packages/*"
```

## Step 2: Configure Turborepo Pipeline

```json
// turbo.json
{
  "$schema": "https://turbo.build/schema.json",
  "globalDependencies": ["**/.env.*local"],
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": [".next/**", "dist/**", "!.next/cache/**"],
      "env": ["DATABASE_URL", "NEXT_PUBLIC_*"]
    },
    "dev": {
      "cache": false,
      "persistent": true
    },
    "test": {
      "dependsOn": ["^build"],
      "outputs": ["coverage/**"]
    },
    "lint": {
      "dependsOn": ["^build"]
    },
    "typecheck": {
      "dependsOn": ["^build"]
    },
    "db:push": {
      "cache": false
    }
  }
}
```

```json
// Root package.json
{
  "name": "my-monorepo",
  "private": true,
  "scripts": {
    "dev": "turbo dev",
    "build": "turbo build",
    "test": "turbo test",
    "lint": "turbo lint",
    "typecheck": "turbo typecheck",
    "format": "biome format --write .",
    "clean": "turbo clean && rm -rf node_modules"
  },
  "devDependencies": {
    "turbo": "^2",
    "@biomejs/biome": "^2"
  },
  "packageManager": "pnpm@9.0.0"
}
```

## Step 3: Shared UI Package

```json
// packages/ui/package.json
{
  "name": "@repo/ui",
  "version": "0.0.0",
  "private": true,
  "exports": {
    "./button": "./src/button.tsx",
    "./card": "./src/card.tsx",
    "./input": "./src/input.tsx",
    "./styles.css": "./src/styles.css"
  },
  "devDependencies": {
    "@repo/config-ts": "workspace:*",
    "react": "^19",
    "react-dom": "^19"
  }
}
```

```tsx
// packages/ui/src/button.tsx
import { forwardRef, type ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

const styles = {
  primary: "bg-blue-600 text-white hover:bg-blue-700",
  secondary: "bg-gray-200 text-gray-900 hover:bg-gray-300",
  ghost: "bg-transparent hover:bg-gray-100",
  danger: "bg-red-600 text-white hover:bg-red-700",
};

const sizes = {
  sm: "px-3 py-1.5 text-sm",
  md: "px-4 py-2 text-base",
  lg: "px-6 py-3 text-lg",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", loading, children, disabled, className, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={`rounded-lg font-medium transition-colors disabled:opacity-50 ${styles[variant]} ${sizes[size]} ${className || ""}`}
      {...props}
    >
      {loading ? <span className="animate-spin mr-2">⏳</span> : null}
      {children}
    </button>
  )
);
```

## Step 4: Consuming Shared Packages

```json
// apps/web/package.json
{
  "name": "@repo/web",
  "dependencies": {
    "@repo/ui": "workspace:*",
    "@repo/db": "workspace:*",
    "next": "^15",
    "react": "^19"
  }
}
```

```tsx
// apps/web/src/app/page.tsx
import { Button } from "@repo/ui/button";
import { Card } from "@repo/ui/card";
import { getProjects } from "@repo/db";

export default async function Home() {
  const projects = await getProjects();

  return (
    <main className="p-8">
      <h1 className="text-3xl font-bold mb-6">Projects</h1>
      <div className="grid gap-4">
        {projects.map((p) => (
          <Card key={p.id}>
            <h2>{p.name}</h2>
            <Button variant="secondary" size="sm">View</Button>
          </Card>
        ))}
      </div>
    </main>
  );
}
```

## Step 5: CI with Remote Caching

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm

      - run: pnpm install --frozen-lockfile

      - name: Build, lint, test (with Turbo remote cache)
        run: pnpm turbo build lint test typecheck
        env:
          TURBO_TOKEN: ${{ secrets.TURBO_TOKEN }}
          TURBO_TEAM: ${{ secrets.TURBO_TEAM }}
```

```bash
# Enable remote caching (one-time setup)
npx turbo login
npx turbo link
```

## Summary

Zara's team works in one repo. Changing a Button component in `packages/ui` is one PR that automatically rebuilds only `@repo/web` and `@repo/api` (because they depend on `@repo/ui`). Unchanged packages serve cached results — a full CI run that took 8 minutes now takes 90 seconds when only one package changed. `pnpm dev` starts both the frontend and API in parallel. No more npm publishing for internal packages, no more cross-repo dependency hell. The shared DB package means schema changes propagate to both apps instantly with full type safety.
