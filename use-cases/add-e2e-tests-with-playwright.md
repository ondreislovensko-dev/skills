---
title: "Add End-to-End Tests with Playwright to Catch Bugs Before Users Do"
slug: add-e2e-tests-with-playwright
description: "Set up Playwright for automated end-to-end testing — write tests for critical user flows, mock APIs, add visual regression checks, and integrate into CI to catch breakages before they reach production."
skills: [playwright-testing, cicd-pipeline, test-generator]
category: development
tags: [playwright, testing, e2e, browser-testing, ci-cd, qa]
---

# Add End-to-End Tests with Playwright to Catch Bugs Before Users Do

## The Problem

Dani is a frontend lead at a 15-person startup building a B2B analytics dashboard. The team ships fast — 3-4 PRs merged daily — but has no end-to-end tests. They rely on manual QA before releases, which means the QA engineer spends 4 hours clicking through flows every Thursday. Despite this, production bugs slip through regularly: last sprint, a CSS change broke the login button on Safari, a refactor silently removed a form validation, and a dashboard filter stopped working after an API response format changed.

The team tried Cypress a year ago but abandoned it — tests were slow, flaky, and broke every time the UI changed because they were coupled to CSS selectors. They need a testing setup that is fast, stable, works across browsers, and does not turn into a maintenance burden.

## The Solution

Using the **playwright-testing**, **test-generator**, and **cicd-pipeline** skills, the agent sets up a robust e2e test suite with auto-waiting locators that resist UI changes, scaffolds tests for critical flows, and wires everything into CI so broken code never reaches main.

## Step-by-Step Walkthrough

### Step 1: Set Up Playwright with the Right Configuration

```text
Set up Playwright for our Next.js analytics dashboard. We need to test on Chromium, Firefox, and WebKit (our users report Safari bugs often). Configure it to: auto-start our dev server (npm run dev on port 3000), capture traces and screenshots only on failure (save CI storage), retry failed tests twice in CI, run tests in parallel locally but sequentially in CI (our CI runner is small). We use TypeScript.
```

The configuration lands in `playwright.config.ts` with the settings that matter most for a small team:

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  workers: process.env.CI ? 1 : undefined,
  retries: process.env.CI ? 2 : 0,
  use: {
    trace: 'on-first-retry',       // Captures timeline, DOM, network — only when needed
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
  webServer: {
    command: 'npm run dev',
    port: 3000,
    reuseExistingServer: !process.env.CI,
  },
});
```

The project structure separates concerns cleanly:

- `tests/e2e/auth.setup.ts` — logs in once, saves the session so every other test reuses it
- `tests/e2e/pages/` — page object models (locators live here, not in tests)
- `tests/e2e/flows/` — user flow tests
- `tests/e2e/visual/` — screenshot comparison tests
- `tests/.auth/` — saved auth state, gitignored

### Step 2: Write Tests for the 5 Most Critical User Flows

```text
Write e2e tests for our most critical flows. Our app is a B2B analytics dashboard. The critical flows are:

1. Login — email/password, should redirect to /dashboard, show user's name in header
2. Dashboard — load default dashboard, verify 4 KPI cards render with numbers (not loading spinners), date range picker works
3. Create report — click "New Report", select metrics (revenue, users, conversion), choose date range, generate report, verify chart renders
4. Filter and export — apply filters (date range, country, device), verify table updates, click Export CSV, verify download starts
5. Team invite — go to Settings > Team, enter email, select role, send invite, verify invite appears in pending list

Use page objects for each page. Use role-based locators (getByRole, getByLabel) not CSS selectors.
```

Every page gets a page object that encapsulates its locators. This is what killed the Cypress setup last time — tests broke because selectors were scattered everywhere. Here, the dashboard page object keeps everything in one place:

```typescript
// tests/e2e/pages/dashboard.page.ts
import { type Page, type Locator } from '@playwright/test';

export class DashboardPage {
  readonly kpiCards: Locator;
  readonly dateRangePicker: Locator;
  readonly newReportButton: Locator;

  constructor(private page: Page) {
    this.kpiCards = page.getByRole('region', { name: /kpi/i });
    this.dateRangePicker = page.getByLabel('Date range');
    this.newReportButton = page.getByRole('button', { name: 'New Report' });
  }

  async verifyKPIsLoaded() {
    // Verify cards show numbers, not loading spinners
    for (const card of await this.kpiCards.all()) {
      await expect(card.getByRole('status')).not.toBeVisible();
      await expect(card.locator('[data-testid="kpi-value"]')).toHaveText(/\d/);
    }
  }
}
```

The test files cover 15 assertions across the 5 flows:

| Flow | Tests | What breaks without them |
|---|---|---|
| Login | Successful redirect, invalid credentials, validation errors | The Safari login button bug from last sprint |
| Dashboard | KPI cards loaded, date picker updates, card navigation | Users staring at infinite spinners |
| Create report | Metric selection, chart rendering, save to sidebar | Reports silently failing to generate |
| Filter + export | Country filter, date range, CSV download | The broken filter from the API change |
| Team invite | Send invite, pending list, duplicate email error | Invites disappearing into the void |

Auth setup runs once and saves `storageState` — no repeated logins across 15 tests. Total runtime across 3 browsers: about 90 seconds in parallel.

### Step 3: Add API Mocking for Edge Cases

```text
Add tests for error states and edge cases using API mocking. Test these scenarios:

1. Dashboard API returns 500 — should show error state with retry button
2. Dashboard API returns empty data — should show "No data for this period" message
3. Report generation takes more than 5 seconds — should show progress indicator
4. Export fails mid-download — should show error toast
5. Session expires while user is on dashboard — should redirect to login

Use Playwright's route mocking, don't hit real APIs for these tests.
```

These are the scenarios no one ever tests manually — and exactly the ones users hit. Playwright's route interception makes them trivial:

```typescript
// tests/e2e/flows/edge-cases.spec.ts
test('API error shows retry button that actually works', async ({ page }) => {
  let callCount = 0;
  await page.route('/api/dashboard', (route) => {
    callCount++;
    if (callCount === 1) return route.fulfill({ status: 500 });
    return route.continue(); // Second call succeeds
  });

  await page.goto('/dashboard');
  await expect(page.getByText('Something went wrong')).toBeVisible();
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByText('Something went wrong')).not.toBeVisible();
});
```

Five edge-case tests, all running without a backend. The session-expiry test mocks a 401 response and verifies the redirect to `/login` with a "Session expired" message. The slow-report test adds a 3-second delay and confirms the progress indicator appears. These run in about 15 seconds total since there is no network wait.

### Step 4: Add Visual Regression Tests

```text
Add visual regression tests that catch unexpected CSS changes. Take screenshots of: the login page, the dashboard with KPI cards, a generated report with chart, and the settings page. Mock API responses to ensure consistent data for screenshots. Configure a 1% pixel diff threshold so minor anti-aliasing differences don't cause failures.
```

Visual tests mock every API call to produce deterministic screenshots — same data, same timestamps, every run. The `maxDiffPixelRatio: 0.01` threshold ignores anti-aliasing noise while catching real layout shifts.

Four pages get baseline screenshots committed to git:

- **login.png** — no auth needed, simplest baseline
- **dashboard.png** — 4 KPI cards with mocked data
- **report-chart.png** — line chart with mocked series data
- **settings-team.png** — team member list with mocked profiles

Snapshots live in `tests/e2e/visual/screenshots.spec.ts-snapshots/` and show up in PR diffs. When a screenshot changes intentionally, one command updates the baselines:

```bash
npx playwright test tests/e2e/visual --update-snapshots
```

### Step 5: Integrate into CI

```text
Create a GitHub Actions workflow that runs the full Playwright suite on every PR to main. Cache the Playwright browsers between runs to speed up CI. Upload the HTML report as an artifact on failure so developers can debug. Add a PR comment that summarizes test results (passed/failed/skipped). The workflow should block merge if any test fails.
```

The workflow caches Playwright browsers between runs (saves about 45 seconds per build) and posts a summary comment on every PR:

```yaml
# .github/workflows/e2e.yml
name: E2E Tests
on: [pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm ci
      - name: Cache Playwright browsers
        uses: actions/cache@v4
        with:
          path: ~/.cache/ms-playwright
          key: playwright-${{ hashFiles('package-lock.json') }}
      - run: npx playwright install --with-deps
      - run: npx playwright test
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
```

On failure, the PR comment links directly to the trace file for the failing test — no guesswork about what happened. Branch protection requires the "E2E Tests" check to pass before merge.

Total CI time: about 3 minutes. That is 3 minutes to test 15 flows across 3 browsers, 5 edge cases, and 4 visual regression checks.

## Real-World Example

Dani's team enables the workflow on a Monday. By Wednesday, the CI catches a PR that breaks the CSV export on Firefox — a `Blob` constructor difference that only manifests in Gecko. Thursday, the visual regression test flags a dashboard layout shift caused by a padding change in a shared component. Neither bug would have survived manual QA either, but both would have shipped on a busy week when "we'll test it later" becomes "we'll fix it in production."

QA time drops from 4 hours per release to 30 minutes of exploratory testing. The QA engineer stops re-checking the same 5 flows and starts finding new bugs — the kind that automated tests cannot catch, like confusing UX flows and misleading copy. Three weeks in, the team has caught 8 regressions before production, and the Thursday release ritual stops feeling like a gamble.
