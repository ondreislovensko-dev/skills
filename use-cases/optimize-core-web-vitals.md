---
title: "Optimize Core Web Vitals with AI"
slug: optimize-core-web-vitals
description: "Diagnose and fix LCP, CLS, and INP issues to pass Google's Core Web Vitals thresholds and improve user experience."
skills: [web-vitals-analyzer, frontend-design, code-reviewer]
category: development
tags: [performance, web-vitals, lighthouse, frontend, seo]
---

# Optimize Core Web Vitals with AI

## The Problem

Google Search Console shows 340 product pages failing Core Web Vitals. Lighthouse gives the site a score of 34 and a wall of suggestions — "reduce unused JavaScript," "avoid enormous network payloads," "eliminate render-blocking resources" — but no prioritization, no root cause analysis, and no indication of which fix will actually move the needle.

The frontend engineer tries the obvious things: `loading="lazy"` on images, WebP conversion, tree-shaking unused imports. The score barely moves. The real bottleneck turns out to be a render-blocking CSS file nobody noticed, buried in the `<head>` behind three other stylesheets. Organic traffic has dropped 18% over the past quarter, and the team suspects the CWV penalty is partly to blame.

The core difficulty: frontend performance optimization requires understanding the interaction between resource loading, the rendering pipeline, and JavaScript execution. Most developers don't have time to become browser internals experts. And Lighthouse's flat list of suggestions treats a 50ms improvement the same as a 3-second one.

## The Solution

Using the **web-vitals-analyzer**, **frontend-design**, and **code-reviewer** skills, the approach is to trace the critical rendering path, identify the exact LCP element, pinpoint layout shift sources, profile main thread bottlenecks causing poor INP, and produce a prioritized fix list with estimated metric improvements for each change.

## Step-by-Step Walkthrough

### Step 1: Get the Baseline Diagnosis

```text
Analyze the Core Web Vitals for our product page. Here's the Lighthouse JSON
report and the page source from src/pages/product/[id].tsx. Tell me exactly
what's failing and why.
```

The Lighthouse report and source code reveal three failing metrics:

| Metric | Current | Target | Status | Primary Source |
|---|---|---|---|---|
| LCP | 4.8s | < 2.5s | Failing | Hero product image |
| CLS | 0.28 | < 0.1 | Failing | Image + review stars + pricing badge |
| INP | 340ms | < 200ms | Failing | "Add to Cart" button re-render |

Twelve issues across the three metrics, but five account for nearly all the impact:

1. **Hero image** — 1.8MB JPEG, lazy-loaded (wrong for above-fold content), no preload hint, no width/height attributes. Affects both LCP and CLS.
2. **Four render-blocking CSS files** totaling 220KB in the `<head>`. Delays first paint by almost a second.
3. **Cart state update** re-renders the entire page because `CartProvider` wraps everything with no memoization. 847 components re-render on every "Add to Cart" click.
4. **Review stars component** loads 47KB of JavaScript and shifts layout on hydration — the skeleton placeholder is 20px tall but the real component renders at 32px.
5. **Third-party chat widget** blocks the main thread for 280ms on load.

### Step 2: Fix LCP — The Biggest Impact First

```text
Show me exactly how to fix the hero image and render-blocking CSS.
Give me the code changes.
```

**Fix 1: Hero product image** (estimated LCP improvement: -2.8s)

The image is lazy-loaded, which tells the browser to deprioritize it. For the largest element on the page, that's exactly backwards. Replace the lazy load with high-priority fetch and add explicit dimensions:

```html
<!-- Before (src/pages/product/[id].tsx:34) -->
<img src={product.imageUrl} loading="lazy" alt={product.name} />

<!-- After -->
<img
  src={product.imageUrl.replace('.jpg', '.webp')}
  alt={product.name}
  width={800}
  height={600}
  fetchpriority="high"
  decoding="async"
/>
```

Add a preload hint in `src/pages/_document.tsx` so the browser starts fetching the image before it even parses the page body:

```html
<link rel="preload" as="image" type="image/webp"
      href="/api/product-image?format=webp&w=800" />
```

**Fix 2: Render-blocking CSS** (estimated LCP improvement: -0.9s)

Four `<link rel="stylesheet">` tags in the `<head>` block rendering until all 220KB loads. Most of that CSS styles below-the-fold content. Inline the critical above-fold styles (~8KB) directly in a `<style>` tag, then load the rest asynchronously:

```html
<link rel="stylesheet" href="/styles/animations.css"
      media="print" onload="this.media='all'" />
<link rel="stylesheet" href="/styles/below-fold.css"
      media="print" onload="this.media='all'" />
```

Combined expected LCP: **4.8s down to roughly 1.6s**.

### Step 3: Fix CLS — Stop the Layout Shifts

```text
Fix the 0.28 CLS score. Show me every element causing shifts
and the exact CSS changes needed.
```

Three elements contribute to the 0.28 CLS score:

**Shift 1: Product image (contribution: 0.15)** — already fixed above. The `width` and `height` attributes let the browser reserve space before the image loads.

**Shift 2: Review stars component (contribution: 0.08)** — the skeleton renders at 20px height, but the hydrated component expands to 32px. Fix with an explicit container height in `src/components/ReviewStars.tsx`:

```jsx
<div style={{ minHeight: '32px' }} className="review-stars">
  <ReviewStars rating={product.rating} />
</div>
```

**Shift 3: Dynamic pricing badge (contribution: 0.05)** — the "20% OFF" badge injects above the price after an API response, pushing content down. Reserve the space unconditionally in `src/components/PricingBadge.tsx`:

```jsx
<div className="pricing-badge-slot" style={{ minHeight: '28px' }}>
  {discount && <PricingBadge discount={discount} />}
</div>
```

Expected CLS: **0.28 down to roughly 0.04**.

### Step 4: Fix INP — Make Interactions Feel Instant

```text
The Add to Cart button has 340ms INP. Profile what's happening on click
and show me how to fix it.
```

A main thread trace of the "Add to Cart" click reveals where the 340ms goes:

| Time | What Happens |
|---|---|
| 0-12ms | Event handler fires, calls `addToCart(productId)` |
| 12-180ms | Zustand store update triggers re-render of `CartProvider`, which wraps the entire page — 847 components re-render |
| 180-290ms | Cart drawer animation runs synchronous layout calculation via `getBoundingClientRect()` |
| 290-340ms | Analytics tracking runs synchronously |

**Fix 1: Scope cart re-renders (saves ~160ms)** — Move `CartProvider` to wrap only the cart drawer, not the full page. Use Zustand selectors to subscribe to specific slices:

```javascript
// Before (re-renders on ANY cart change):
const cart = useCartStore();

// After (re-renders only when item count changes):
const itemCount = useCartStore((s) => s.items.length);
```

**Fix 2: Defer analytics (saves ~50ms):**

```javascript
requestIdleCallback(() => analytics.track('add_to_cart', { productId }));
```

**Fix 3: CSS animation instead of JS layout calculation (saves ~60ms)** — Replace the `getBoundingClientRect()` call with a CSS transform animation for the cart drawer.

Expected INP: **340ms down to roughly 80ms**.

## Real-World Example

The engineer implements the top three fixes — hero image optimization, CSS inlining, and cart re-render scoping — in a single afternoon. About 2 hours of work.

After deployment, the Lighthouse score jumps from 34 to 91. LCP drops to 1.4s, CLS to 0.03, INP to 75ms. All three metrics are now solidly in the "Good" range.

Within 28 days, Google reclassifies all 340 product pages as passing Core Web Vitals. Organic traffic begins recovering from the 18% dip. The "performance epic" that was being scoped as a two-sprint project — with investigation, planning, and implementation phases — turns out to be one afternoon of targeted fixes. The difference: knowing exactly which 3 of the 12 issues to fix first, and having the exact code changes instead of vague Lighthouse suggestions.
