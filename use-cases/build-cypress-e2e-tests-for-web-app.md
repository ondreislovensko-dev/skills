---
title: Build Cypress E2E Tests for a Web App
slug: build-cypress-e2e-tests-for-web-app
description: >-
  Write end-to-end tests with Cypress for critical user flows — authentication,
  checkout, form submission, API mocking, and visual testing with CI integration
  for reliable deployments.
skills:
  - cypress
  - github-actions
category: testing
tags:
  - e2e-testing
  - cypress
  - testing
  - automation
  - quality
---

# Build Cypress E2E Tests for a Web App

Jess deploys her e-commerce app twice a week and spends 2 hours manually testing before each deploy: login, add to cart, checkout, search, filters, account settings. She misses regressions because she can't test every path. Cypress automates these critical flows — tests run in a real browser, interact with the app like a user would, and catch breakage in CI before it reaches production.

## Step 1: Install and Configure

```bash
npm install -D cypress @testing-library/cypress
npx cypress open  # First run creates the directory structure
```

```typescript
// cypress.config.ts
import { defineConfig } from "cypress";

export default defineConfig({
  e2e: {
    baseUrl: "http://localhost:3000",
    viewportWidth: 1280,
    viewportHeight: 720,
    video: true,
    screenshotOnRunFailure: true,
    retries: { runMode: 2, openMode: 0 },
    defaultCommandTimeout: 10000,
    setupNodeEvents(on, config) {
      // Seed database before tests
      on("task", {
        async seedDatabase() {
          const { execSync } = require("child_process");
          execSync("npx prisma db seed", { env: { ...process.env, DATABASE_URL: config.env.DATABASE_URL } });
          return null;
        },
        async clearDatabase() {
          const { execSync } = require("child_process");
          execSync("npx prisma migrate reset --force", { env: { ...process.env, DATABASE_URL: config.env.DATABASE_URL } });
          return null;
        },
      });
    },
  },
});
```

```typescript
// cypress/support/commands.ts
import "@testing-library/cypress/add-commands";

declare global {
  namespace Cypress {
    interface Chainable {
      login(email?: string, password?: string): void;
      addToCart(productId: string): void;
    }
  }
}

// Reusable login command — uses API to skip UI for speed
Cypress.Commands.add("login", (email = "test@example.com", password = "testpassword123") => {
  cy.session([email], () => {
    cy.request("POST", "/api/auth/login", { email, password }).then((resp) => {
      expect(resp.status).to.eq(200);
    });
  });
});

Cypress.Commands.add("addToCart", (productId: string) => {
  cy.request("POST", "/api/cart/items", { productId, quantity: 1 });
});
```

## Step 2: Authentication Flow Tests

```typescript
// cypress/e2e/auth.cy.ts
describe("Authentication", () => {
  beforeEach(() => {
    cy.task("seedDatabase");
  });

  it("signs up a new user", () => {
    cy.visit("/signup");
    cy.findByLabelText("Email").type("new@example.com");
    cy.findByLabelText("Password").type("securepassword123");
    cy.findByLabelText("Confirm Password").type("securepassword123");
    cy.findByRole("button", { name: /sign up/i }).click();

    cy.url().should("include", "/onboarding");
    cy.findByText(/welcome/i).should("be.visible");
  });

  it("logs in with valid credentials", () => {
    cy.visit("/login");
    cy.findByLabelText("Email").type("test@example.com");
    cy.findByLabelText("Password").type("testpassword123");
    cy.findByRole("button", { name: /sign in/i }).click();

    cy.url().should("include", "/dashboard");
    cy.findByText("test@example.com").should("be.visible");
  });

  it("shows error for invalid credentials", () => {
    cy.visit("/login");
    cy.findByLabelText("Email").type("test@example.com");
    cy.findByLabelText("Password").type("wrongpassword");
    cy.findByRole("button", { name: /sign in/i }).click();

    cy.findByText(/invalid email or password/i).should("be.visible");
    cy.url().should("include", "/login");
  });

  it("redirects unauthenticated users to login", () => {
    cy.visit("/dashboard");
    cy.url().should("include", "/login");
    cy.url().should("include", "redirect=%2Fdashboard");
  });
});
```

## Step 3: E-Commerce Checkout Flow

```typescript
// cypress/e2e/checkout.cy.ts
describe("Checkout Flow", () => {
  beforeEach(() => {
    cy.task("seedDatabase");
    cy.login();
  });

  it("completes full purchase flow", () => {
    // Browse products
    cy.visit("/products");
    cy.findByPlaceholderText("Search products").type("headphones");
    cy.findByText("Wireless Headphones").should("be.visible");

    // Add to cart
    cy.findByText("Wireless Headphones").click();
    cy.findByRole("button", { name: /add to cart/i }).click();
    cy.findByText("Added to cart").should("be.visible");

    // Verify cart
    cy.findByTestId("cart-badge").should("contain", "1");
    cy.findByTestId("cart-icon").click();
    cy.findByText("Wireless Headphones").should("be.visible");
    cy.findByText("$79.99").should("be.visible");

    // Checkout
    cy.findByRole("button", { name: /checkout/i }).click();
    cy.url().should("include", "/checkout");

    // Fill shipping
    cy.findByLabelText("Full Name").type("Test User");
    cy.findByLabelText("Address").type("123 Test St");
    cy.findByLabelText("City").type("Testville");
    cy.findByLabelText("ZIP Code").type("12345");

    // Mock Stripe payment (don't hit real Stripe in tests)
    cy.intercept("POST", "/api/payments/create-intent", {
      statusCode: 200,
      body: { clientSecret: "pi_test_secret" },
    });

    cy.intercept("POST", "/api/orders", {
      statusCode: 201,
      body: { orderId: "order_test_123" },
    }).as("createOrder");

    cy.findByRole("button", { name: /place order/i }).click();
    cy.wait("@createOrder");

    // Order confirmation
    cy.url().should("include", "/orders/order_test_123");
    cy.findByText(/order confirmed/i).should("be.visible");
    cy.findByText("order_test_123").should("be.visible");
  });

  it("handles out-of-stock items", () => {
    cy.addToCart("product-out-of-stock");
    cy.visit("/cart");
    cy.findByText(/out of stock/i).should("be.visible");
    cy.findByRole("button", { name: /checkout/i }).should("be.disabled");
  });
});
```

## Step 4: API Mocking for Edge Cases

```typescript
// cypress/e2e/error-handling.cy.ts
describe("Error Handling", () => {
  beforeEach(() => {
    cy.login();
  });

  it("shows friendly error on API failure", () => {
    cy.intercept("GET", "/api/products*", {
      statusCode: 500,
      body: { error: "Internal server error" },
    });

    cy.visit("/products");
    cy.findByText(/something went wrong/i).should("be.visible");
    cy.findByRole("button", { name: /try again/i }).should("be.visible");
  });

  it("handles network timeout gracefully", () => {
    cy.intercept("GET", "/api/products*", {
      forceNetworkError: true,
    });

    cy.visit("/products");
    cy.findByText(/unable to connect/i).should("be.visible");
  });
});
```

## Step 5: CI Integration

```yaml
# .github/workflows/e2e.yml
name: E2E Tests
on: [pull_request]

jobs:
  cypress:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_DB: test, POSTGRES_USER: test, POSTGRES_PASSWORD: test }
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm }
      - run: npm ci
      - run: npx prisma migrate deploy
        env: { DATABASE_URL: "postgresql://test:test@localhost:5432/test" }
      - uses: cypress-io/github-action@v6
        with:
          build: npm run build
          start: npm start
          wait-on: http://localhost:3000
          wait-on-timeout: 120
        env:
          DATABASE_URL: "postgresql://test:test@localhost:5432/test"
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: cypress-videos
          path: cypress/videos
```

## Summary

Jess replaced 2 hours of manual testing with a 5-minute Cypress run. The tests cover her critical paths: signup, login, product search, cart management, and checkout — with API mocking for payment and error scenarios. The `cy.session()` command caches auth state so tests don't re-login for every test. CI runs E2E tests on every PR with a real PostgreSQL database, and failing tests upload video recordings for debugging. She deploys with confidence because if the checkout flow breaks, the PR can't merge.
