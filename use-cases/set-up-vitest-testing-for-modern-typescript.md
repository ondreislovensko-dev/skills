---
title: Set Up Vitest Testing for Modern TypeScript Projects
slug: set-up-vitest-testing-for-modern-typescript
description: >-
  Configure Vitest for fast unit and integration testing in TypeScript — set up
  test utilities, mocking strategies, code coverage, snapshot testing, and CI
  integration for a production codebase.
skills:
  - vitest
  - testing-library
  - github-actions
category: testing
tags:
  - testing
  - vitest
  - typescript
  - unit-testing
  - ci
---

# Set Up Vitest Testing for Modern TypeScript Projects

Kai's team writes TypeScript but has zero tests. Every deploy is a prayer. They tried Jest before but the ESM/TypeScript configuration was a nightmare. Vitest runs natively on Vite's transform pipeline — zero config for TypeScript, ESM support out of the box, and it's 10x faster than Jest. He wants unit tests for business logic, integration tests for API routes, and component tests for React — all in one framework.

## Step 1: Install and Configure

```bash
npm install -D vitest @vitest/coverage-v8 @vitest/ui happy-dom
npm install -D @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

```typescript
// vitest.config.ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  test: {
    globals: true,
    environment: "happy-dom",
    setupFiles: ["./tests/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}", "tests/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.*", "src/**/*.stories.*", "src/types/**"],
      thresholds: {
        statements: 80,
        branches: 75,
        functions: 80,
        lines: 80,
      },
    },
    pool: "forks",
    testTimeout: 10000,
  },
});
```

```typescript
// tests/setup.ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// Mock environment variables
vi.stubEnv("DATABASE_URL", "postgresql://test:test@localhost:5432/test");
vi.stubEnv("JWT_SECRET", "test-secret-key");
```

## Step 2: Unit Tests for Business Logic

```typescript
// src/lib/pricing.ts
export function calculatePrice(plan: "free" | "pro" | "enterprise", seats: number, annual: boolean): number {
  const basePrices = { free: 0, pro: 29, enterprise: 99 };
  const base = basePrices[plan];
  const seatPrice = plan === "free" ? 0 : base * seats;
  const discount = annual ? 0.8 : 1; // 20% annual discount
  return Math.round(seatPrice * discount * 100) / 100;
}
```

```typescript
// src/lib/pricing.test.ts
import { describe, it, expect } from "vitest";
import { calculatePrice } from "./pricing";

describe("calculatePrice", () => {
  it("returns 0 for free plan regardless of seats", () => {
    expect(calculatePrice("free", 100, false)).toBe(0);
    expect(calculatePrice("free", 100, true)).toBe(0);
  });

  it("calculates monthly pro pricing per seat", () => {
    expect(calculatePrice("pro", 1, false)).toBe(29);
    expect(calculatePrice("pro", 5, false)).toBe(145);
  });

  it("applies 20% annual discount", () => {
    expect(calculatePrice("pro", 1, true)).toBe(23.2);
    expect(calculatePrice("enterprise", 10, true)).toBe(792);
  });

  it.each([
    { plan: "pro" as const, seats: 3, annual: false, expected: 87 },
    { plan: "enterprise" as const, seats: 1, annual: true, expected: 79.2 },
  ])("calculates $plan with $seats seats (annual=$annual) = $expected", ({ plan, seats, annual, expected }) => {
    expect(calculatePrice(plan, seats, annual)).toBe(expected);
  });
});
```

## Step 3: Mocking External Services

```typescript
// src/services/email.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { sendWelcomeEmail } from "./email";

// Mock the Resend module
vi.mock("resend", () => ({
  Resend: vi.fn().mockImplementation(() => ({
    emails: {
      send: vi.fn().mockResolvedValue({ id: "email_123" }),
    },
  })),
}));

describe("sendWelcomeEmail", () => {
  it("sends email with correct parameters", async () => {
    const { Resend } = await import("resend");
    const result = await sendWelcomeEmail("user@example.com", "Kai");

    expect(result.id).toBe("email_123");
    const mockInstance = vi.mocked(Resend).mock.results[0].value;
    expect(mockInstance.emails.send).toHaveBeenCalledWith(
      expect.objectContaining({
        to: "user@example.com",
        subject: expect.stringContaining("Welcome"),
      })
    );
  });
});
```

```typescript
// src/db/queries.test.ts — Testing database queries with mocked db
import { describe, it, expect, vi } from "vitest";
import { getUserByEmail } from "./queries";

vi.mock("../db", () => ({
  db: {
    query: {
      users: {
        findFirst: vi.fn(),
      },
    },
  },
}));

describe("getUserByEmail", () => {
  it("returns null for non-existent user", async () => {
    const { db } = await import("../db");
    vi.mocked(db.query.users.findFirst).mockResolvedValue(undefined);

    const result = await getUserByEmail("ghost@example.com");
    expect(result).toBeNull();
  });
});
```

## Step 4: React Component Tests

```typescript
// src/components/TaskCard.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaskCard } from "./TaskCard";

const mockTask = {
  id: "1",
  title: "Fix login bug",
  status: "todo" as const,
  assignee: { name: "Kai", avatar: "🧑‍💻" },
  priority: "high" as const,
};

describe("TaskCard", () => {
  it("renders task details", () => {
    render(<TaskCard task={mockTask} onStatusChange={vi.fn()} />);

    expect(screen.getByText("Fix login bug")).toBeInTheDocument();
    expect(screen.getByText("Kai")).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("calls onStatusChange when status button clicked", async () => {
    const user = userEvent.setup();
    const onStatusChange = vi.fn();
    render(<TaskCard task={mockTask} onStatusChange={onStatusChange} />);

    await user.click(screen.getByRole("button", { name: /mark as in progress/i }));
    expect(onStatusChange).toHaveBeenCalledWith("1", "in_progress");
  });

  it("shows priority badge with correct color", () => {
    render(<TaskCard task={mockTask} onStatusChange={vi.fn()} />);
    const badge = screen.getByText("high");
    expect(badge).toHaveClass("bg-red-100");
  });
});
```

## Step 5: CI Integration with GitHub Actions

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm

      - run: npm ci

      - name: Run tests with coverage
        run: npx vitest run --coverage

      - name: Upload coverage
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: coverage-report
          path: coverage/
```

```json
// package.json scripts
{
  "scripts": {
    "test": "vitest",
    "test:run": "vitest run",
    "test:coverage": "vitest run --coverage",
    "test:ui": "vitest --ui --open"
  }
}
```

## Summary

Kai's team went from zero tests to 80% coverage in two weeks. Vitest runs their 200 tests in 3 seconds (Jest took 25 seconds on the same suite). TypeScript works out of the box — no `ts-jest` config, no transform maps. The `vi.mock()` API handles external services cleanly, Testing Library keeps component tests focused on user behavior, and GitHub Actions runs coverage on every PR. The Vitest UI (`--ui`) gives them a visual test runner during development that shows test results in real-time as they edit code.
