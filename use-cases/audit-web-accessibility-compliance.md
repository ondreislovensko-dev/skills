---
title: "Audit Web Accessibility Compliance with AI"
slug: audit-web-accessibility-compliance
description: "Systematically find and fix WCAG 2.2 accessibility violations across your application before regulatory deadlines hit."
skills: [accessibility-auditor, code-reviewer, frontend-design]
category: development
tags: [accessibility, wcag, compliance, a11y, european-accessibility-act]
---

# Audit Web Accessibility Compliance with AI

## The Problem

The European Accessibility Act takes effect in June 2025, ADA lawsuits against web properties hit a record 4,600+ in 2024, and your product has never had a formal accessibility audit. You know there are issues — the login form uses placeholder text instead of labels, the navigation dropdown traps keyboard focus, and color contrast is inconsistent — but manually auditing 80+ pages against 50 WCAG 2.2 success criteria would take weeks. Automated tools like axe catch only about 30% of violations, and the remaining 70% require human judgment about whether ARIA patterns are correct, focus management works properly, and screen reader announcements make sense.

The cost of inaction is concrete. An accessibility lawsuit averages $25,000-$50,000 in settlement costs. The European Accessibility Act carries fines per violation. And enterprise clients increasingly require WCAG compliance as a procurement prerequisite — one failed audit can block a six-figure contract.

## The Solution

Feed your components and page templates to the AI agent for a deep accessibility audit. It goes beyond automated scanners — analyzing keyboard interaction patterns, ARIA semantics, focus management in modals and dynamic content, and color contrast computations — to produce a prioritized violation report with exact code fixes for each issue.

## Step-by-Step Walkthrough

### Step 1: Audit the Most Critical User Flows First

```text
Audit the accessibility of our signup flow: src/pages/signup.tsx, src/components/SignupForm.tsx, and src/components/PasswordStrength.tsx. Check against WCAG 2.2 Level AA. This needs to be compliant before June.
```

The audit of three files reveals 14 violations: 5 Critical, 6 Major, 3 Minor. The critical findings are the ones that make the signup flow completely unusable for assistive technology users — not degraded, but actually broken:

**WCAG 1.3.5 — Autocomplete missing on all 4 form fields.** Users with motor disabilities rely on autofill to avoid retyping their name and email on every site. Without `autocomplete` attributes, the browser cannot help them. This is also one of the easiest fixes — four attributes added to four inputs.

```html
<!-- Before -->
<input name="email" type="email" />

<!-- After — autocomplete values match the HTML spec exactly -->
<input name="name" autoComplete="name" />
<input name="email" autoComplete="email" />
<input name="password" autoComplete="new-password" />
<input name="confirm" autoComplete="new-password" />
```

**WCAG 3.3.2 — Password field has no visible label.** The placeholder "Create a password" disappears the moment a user clicks into the field. If they get distracted and come back, they have no idea what the field is for. Sighted users can usually guess from context. Screen reader users cannot.

```html
<!-- Before — placeholder is not a label -->
<input placeholder="Create a password" type="password" />

<!-- After — visible, persistent label -->
<label htmlFor="password">Create a password</label>
<input id="password" type="password" />
```

**WCAG 4.1.2 — Password strength meter is invisible to screen readers.** The `PasswordStrength` component renders four colored bars that fill up as the password gets stronger. Visually intuitive. For screen reader users: complete silence. They type a password and get zero feedback about whether it meets requirements. They have to submit the form and wait for a validation error to learn their password is too weak.

```jsx
// Add an aria-live region that announces strength changes as the user types
<div aria-live="polite" className="sr-only">
  Password strength: {strengthLabel} ({score}/4)
</div>
// Plus a visible text label alongside the bars: "Weak" / "Fair" / "Strong" / "Very strong"
```

**WCAG 1.4.1 — Strength meter relies on color alone.** Red, yellow, green bars convey strength. Approximately 8% of males have some form of color vision deficiency, and many cannot distinguish red from green. The fix adds text labels and distinct icons alongside the colors — not replacing color, but supplementing it so color is never the *only* indicator.

**WCAG 3.3.1 — Validation errors not announced.** When form submission fails, error messages appear visually next to the offending fields, but screen readers are never notified. A blind user clicks Submit, nothing seems to happen, and they have no idea why. The fix wraps the error container in `role="alert"` with `aria-live="assertive"` and adds `aria-describedby` on each input to link the error directly to its field.

### Step 2: Fix Critical Issues and Verify

```text
I've implemented the 5 critical fixes. Review my changes in the git diff and check if the ARIA patterns are correct.
```

Four out of five fixes are correctly implemented. One subtle bug: the `aria-live` region in `PasswordStrength.tsx` is inside a conditionally rendered block. When strength changes from null to "Weak," the entire region mounts for the first time — and screen readers do not announce the initial content of newly mounted `aria-live` regions. It is a well-known gotcha that trips up even experienced developers.

The fix is simple but easy to miss: render the container unconditionally and only change the text inside:

```jsx
// Wrong — mounts/unmounts, so first value is never announced
{strength && (
  <div aria-live="polite" className="sr-only">
    Password strength: {strength}
  </div>
)}

// Correct — always in the DOM, text updates trigger announcements
<div aria-live="polite" className="sr-only">
  {strength ? `Password strength: ${strength}` : ''}
</div>
```

This is exactly the kind of issue that automated scanners miss — axe would see a valid `aria-live` region and report no violation. The problem is behavioral, not structural, and requires understanding how screen readers process DOM mutations.

All other ARIA patterns check out. The `autocomplete` values match the HTML spec, and the `aria-describedby` wiring correctly links each input to its error message.

### Step 3: Audit Remaining Pages Systematically

```text
Now audit these 6 component files that appear on every page: Header.tsx, Footer.tsx, Navigation.tsx, SearchBar.tsx, MobileMenu.tsx, CookieBanner.tsx. These are shared components so fixing them fixes accessibility site-wide.
```

Shared components are the highest-leverage targets — a fix in `Navigation.tsx` improves every single page in the application. The audit finds 23 issues across all 6 files, with three that affect the entire site:

- **Keyboard trap in the mobile menu** — once a keyboard user opens the menu, there is no way to close it without a mouse. Tab cycles endlessly through menu items with no escape. The fix adds Escape key handling, proper focus trapping that stays within the menu while it is open, and returns focus to the menu trigger button on close.

- **Missing skip-to-content link** — keyboard and screen reader users must tab through the entire header (logo, navigation links, search bar, user menu) on every single page before reaching the main content. On a navigation-heavy site, this means 15-20 tab presses before they can interact with what they came for. A single link at the top of the page fixes this:

```html
<a href="#main" class="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:bg-white focus:p-2">
  Skip to content
</a>
```

- **Cookie banner steals focus on every page load** — the banner calls `.focus()` on mount, ripping focus away from wherever the user was. For a returning user who has already dismissed cookies, this is a jarring interruption on every navigation. The fix: only steal focus on first appearance, and use `inert` on the rest of the page while the banner is showing.

### Step 4: Generate a Compliance Report

```text
Generate a WCAG 2.2 Level AA compliance summary showing: total violations found, violations fixed, remaining issues, and our compliance percentage by WCAG principle (Perceivable, Operable, Understandable, Robust).
```

The compliance report breaks down progress by WCAG principle:

| Principle | Found | Fixed | Remaining | Compliance |
|---|---|---|---|---|
| Perceivable (1.x) | 12 | 8 | 4 | 67% |
| Operable (2.x) | 11 | 5 | 6 | 55% |
| Understandable (3.x) | 9 | 4 | 5 | 56% |
| Robust (4.x) | 5 | 2 | 3 | 60% |
| **Total** | **37** | **19** | **18** | **73%** |

Current compliance: 73%, projected to 100% after the remaining 18 fixes. The "Operable" category has the most remaining work because it covers keyboard navigation, focus management, and timing — the interactive behaviors that require careful implementation, not just attribute changes.

Three high-risk items remain that should be prioritized next:

1. **Mobile menu keyboard trap** — affects every mobile keyboard user on every page. This is the most critical remaining issue because it completely blocks a class of users.
2. **Data table missing row and column headers** — screen reader users cannot navigate the table meaningfully. Without `<th>` elements and `scope` attributes, a table that is visually clear becomes an unintelligible stream of values.
3. **Auto-playing carousel with no pause control** — violates WCAG 2.2.2 and is actively hostile to users with vestibular disorders who experience nausea or disorientation from unexpected motion.

## Real-World Example

A frontend engineer at a 30-person HR tech company receives notice that their largest enterprise client requires WCAG 2.2 AA compliance for contract renewal in 90 days. The application has 12 page templates and 45 shared components, none built with accessibility in mind. An external accessibility consultancy quoted 3 months and $40,000 for the audit and remediation.

She starts with the 8 most-used shared components — Header, Footer, Navigation, SearchBar, and four form components — since fixes there cascade to every page. The audit finds 37 violations total, with 11 Critical that make key flows completely unusable for screen reader and keyboard users. The signup flow has no labels. The dashboard has no landmark regions. The data tables have no headers.

Critical fixes for shared components take 3 days of focused work. Because these components appear everywhere, 3 days of effort fixes accessibility issues across every page in the application simultaneously. The agent then audits the 12 page-specific templates, finding 14 additional issues — mostly missing form labels, inadequate focus management in modals, and two date pickers that are completely inaccessible to keyboard users.

After 2 weeks, all violations are resolved. Manual testing with VoiceOver and NVDA confirms the fixes work in practice, not just in theory — a screen reader user can complete every critical flow from signup through daily use without hitting a dead end. The compliance report goes to the enterprise client, the contract is renewed, and what was estimated as a 3-month, $40,000 project is done in 2 weeks of internal engineering time.
