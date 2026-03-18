---
title: "Set Up Automated Accessibility Regression Testing with AI"
slug: set-up-automated-accessibility-regression-testing
description: "Build a CI pipeline that catches accessibility regressions before they reach production using automated testing."
skills: [test-generator, cicd-pipeline, coding-agent]
category: development
tags: [accessibility, regression-testing, a11y, ci-cd, testing]
---

# Set Up Automated Accessibility Regression Testing with AI

## The Problem

Sofia is the frontend lead at a 25-person health tech startup. Six months ago, the team did a thorough accessibility audit and fixed 73 issues to reach WCAG 2.1 AA compliance. It took two weeks of focused work and felt like a real accomplishment.

Since then, new features have quietly undone that work. A modal was added without keyboard trap management -- users who navigate with a keyboard get stuck inside it. A new dashboard uses color alone to indicate status (red for critical, green for healthy), which is invisible to the 8% of men with color vision deficiency. Form error messages lost their `aria-live` attributes during a refactor, so screen readers don't announce validation errors.

Nobody notices until a customer complains, and by then the damage is compounding. The team doesn't want to pay for quarterly manual audits at $8,000 each, but without automated checks, compliance slowly erodes after every sprint. Every new feature is a risk of introducing another invisible regression.

## The Solution

Use the **test-generator** skill to create accessibility-focused test cases that catch regressions in key user flows, the **cicd-pipeline** skill to integrate them as a required CI check, and the **coding-agent** to write custom testing utilities that go beyond what axe-core catches out of the box -- things like keyboard navigation flow, focus management, and screen reader announcement verification.

## Step-by-Step Walkthrough

### Step 1: Baseline the Current Accessibility State

Before catching regressions, the system needs to know what's already there. A baseline scan of every page captures the known state so future runs can distinguish new violations from accepted ones.

```text
Run an accessibility audit on our web app. Test all pages listed in our sitemap. Capture every WCAG 2.1 AA violation with its severity, element, and page. Save this as our baseline -- future tests should catch any new violations that aren't in this baseline.
```

The scan covers 34 pages and produces a baseline file (`a11y/baseline.json`):

- **0 critical violations** -- the hard work from six months ago holds for the most severe category
- **3 serious violations** -- known issues tracked in the backlog, accepted for now
- **8 moderate violations** -- cosmetic issues that don't block functionality

Total elements tested: 4,271. The 11 known issues go into the baseline. From this point forward, the system will only alert on violations that aren't in this file -- new problems introduced by new code.

### Step 2: Generate Accessibility Regression Tests

Generic page-level scans catch the obvious stuff. Flow-specific tests catch the subtle problems -- like a checkout flow where the "Place Order" button isn't reachable by keyboard, or a settings page where toggling a switch doesn't announce the state change to screen readers.

```text
Generate accessibility tests for our key user flows: signup, login, dashboard, settings, and checkout. Test keyboard navigation, screen reader compatibility, color contrast, and form labeling.
```

Twenty-eight tests across five flows:

**Signup flow** (6 tests): Every form field has a visible label and programmatic association. Error messages have `aria-live="assertive"` so screen readers announce them immediately. The submit button is reachable via Tab and activatable via Enter. Password requirements are exposed to assistive technology, not just visual text.

**Login flow** (4 tests): Focus moves to the first form field on page load. Error states (wrong password, account locked) are announced, not just displayed. The password visibility toggle has an accessible label that updates when toggled.

**Dashboard** (7 tests): Charts have meaningful alt text that conveys the data, not just "chart image." Status indicators use icons and text in addition to color. Data tables have proper header associations so screen readers can announce "Row 3, Column: Status, Value: Active" instead of just "Active."

**Settings** (5 tests): Toggle switches announce their state change ("notifications: on"). Form groups use `fieldset` and `legend`. The save confirmation is announced to screen readers via a live region.

**Checkout** (6 tests): Price totals are readable by screen readers (not just styled text). Address autocomplete results are keyboard-navigable. Focus returns to a logical position after adding or removing items.

### Step 3: Integrate into the CI Pipeline

Tests that don't run automatically don't run at all. The accessibility suite becomes a required check on every pull request.

```text
Add accessibility testing as a required CI check that runs on every PR and blocks merge for new critical or serious violations.
```

The GitHub Actions workflow (`.github/workflows/a11y-tests.yml`) runs in four stages:

1. **axe-core scan** on all 34 pages -- catches common violations (missing alt text, insufficient contrast, missing form labels) in about 90 seconds
2. **Custom a11y test suite** -- runs the 28 flow-specific tests covering keyboard navigation, screen reader compatibility, and focus management
3. **Baseline comparison** -- diffs results against `a11y/baseline.json`, flagging only new violations. Known issues don't create noise.
4. **PR comment** -- posts results directly on the pull request with violation details and fix suggestions

Blocking rules: any new critical or serious violation fails the build. New moderate violations are flagged in the PR comment but don't block merge -- they go into the backlog for the next sprint.

### Step 4: Catch Regressions in Pull Requests

Here's what it looks like in practice. A developer submits a PR that adds a status indicator dashboard widget. The CI runs, and the accessibility check posts a comment:

> **New accessibility violation detected in this PR**
>
> **Page**: `/dashboard`
> **Element**: `<div class="status-indicator">`
> **Rule**: `color-contrast` (serious)
> **Issue**: Insufficient contrast ratio 2.8:1 (minimum 4.5:1)
> **Fix**: Change text color from `#999` to `#767676` or darker
>
> This issue was not in the baseline. Please fix before merging.

The developer sees the exact element, the specific problem, the required threshold, and a concrete fix suggestion. No hunting through logs, no guessing what went wrong. The fix takes 30 seconds: change the color value, push, and the check goes green.

### Step 5: Generate Fix Suggestions for Each Violation

When violations accumulate over a sprint (in the moderate/non-blocking category), the agent can generate developer-friendly fix guides with before/after examples.

```text
For each new violation caught in the last sprint, generate a code fix suggestion with before/after examples and link to the relevant WCAG criterion.
```

Each fix suggestion includes the specific code change needed, a before/after comparison, and a link to the relevant WCAG success criterion so the developer understands the "why" -- not just the "what." A form field missing its label gets a three-line fix and a link to WCAG 1.3.1 (Info and Relationships). A color-only indicator gets a suggestion to add an icon and text alongside the color, with a link to WCAG 1.4.1 (Use of Color).

This turns accessibility fixes from research projects into copy-paste tasks. Developers don't need to become WCAG experts -- they need to know what line to change and why it matters.

## Real-World Example

Sofia sets up the baseline scan on a Monday. The 11 known issues go into the accepted baseline, and the 28 flow-specific tests go into CI as a required check.

Within two weeks, the system catches its first regression: a new modal component lacks focus trapping. A keyboard user who Tabs past the last button in the modal lands on the page behind it instead of cycling back to the top of the modal. The CI comment explains the problem, suggests adding a focus trap library, and links to the WCAG 2.4.3 success criterion. The developer fixes it in the same PR -- it never reaches production.

Over three months, the automated tests catch 9 regressions at the PR stage. A chart without alt text. A toggle switch that doesn't announce state changes. A form that lost its error announcements during a component library upgrade. All caught before merge, all fixed in minutes instead of discovered weeks later by a customer or an $8,000 audit.

Zero new accessibility issues reach production in that three-month window. The quarterly audit that used to find dozens of regressions finds none. Sofia's team maintains WCAG 2.1 AA compliance without thinking about it -- the CI pipeline does the thinking for them.
