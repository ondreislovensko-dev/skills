---
title: "Migrate from Client-Side Rendering to SSR/SSG for SEO and Performance"
slug: migrate-csr-to-ssr-ssg
description: "Transform a client-side React app into a high-performance, SEO-optimized site using Server-Side Rendering and Static Site Generation to improve Core Web Vitals and search rankings."
skills: [ssr-migration, frontend-design, docker-helper]
category: development
tags: [ssr, ssg, seo, performance, react, nextjs, web-vitals, migration]
---

# Migrate from Client-Side Rendering to SSR/SSG for SEO and Performance

## The Problem

Elena, front-end lead at a 55-person B2B SaaS company, watches their marketing site's Google Search Console rankings plummet month after month. Their React SPA loads with a blank white screen for 4.2 seconds while JavaScript bundles download and parse. PageSpeed Insights gives them 31/100 on mobile, with Largest Contentful Paint at 7.1 seconds -- nearly triple the 2.5-second threshold for Core Web Vitals.

The SEO damage is brutal: product pages rank on page 3-4 despite having better content than competitors. Organic traffic dropped 67% over 18 months as Google increasingly penalizes slow sites. Their $120K/year SEO consultant's report is damning: "JavaScript-dependent content invisible to search bots. Recommend complete technical overhaul."

The business numbers tell the rest of the story. Conversion rates on marketing pages dropped from 8.2% to 3.1% as bounce rates hit 73%. Mobile performance is even worse -- 11.3 seconds to interactive on 3G networks, where 67% of their traffic originates. The sales team reports that prospects mention "your website feels slow" during demos. Each 1-second improvement in load time correlates with 12% higher conversion rates in their industry.

## The Solution

Using the **ssr-migration** skill for React-to-Next.js conversion, **frontend-design** for performance optimization, and **docker-helper** for deployment infrastructure, the agent migrates from client-side rendering to a hybrid SSR/SSG architecture -- static generation for marketing content, server rendering for dynamic pages -- and optimizes every Core Web Vital along the way.

## Step-by-Step Walkthrough

### Step 1: Audit Performance and Plan the Migration Strategy

```text
Audit our React SPA's performance and SEO issues. The app has 47 pages:
12 marketing pages (static content), 18 product feature pages (semi-static),
8 blog pages (static), 6 customer case studies (static), and 3 dynamic
pricing/demo request pages. Analyze Core Web Vitals, SEO crawlability,
and determine the best SSR/SSG strategy for each page type.
```

The audit exposes the full extent of the problem:

**Performance (mobile):**

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| First Contentful Paint | 4.8s | <1.8s | Failing |
| Largest Contentful Paint | 7.1s | <2.5s | Failing |
| First Input Delay | 340ms | <100ms | Failing |
| Cumulative Layout Shift | 0.23 | <0.1 | Failing |
| JavaScript bundle size | 847 KB | <200 KB | 4x over budget |

**SEO crawlability:** only 23% of pages successfully indexed. Meta descriptions missing on 89% of pages (generated client-side, invisible to crawlers). No Open Graph tags, no schema markup, no structured data for rich snippets.

The migration strategy splits 47 pages into two groups:

- **SSG (38 pages):** marketing pages, product features (with ISR on 24-hour revalidation), blog posts, and case studies -- all pre-rendered at build time
- **SSR (9 pages):** pricing calculator, demo request forms, and user dashboard -- server-rendered with edge caching

### Step 2: Migrate to Next.js with Static Generation

```text
Convert our React SPA to Next.js with static site generation for all marketing,
product, and blog pages. Optimize images, implement proper meta tags and schema
markup, and ensure all static content pre-renders at build time. Include
automatic sitemap generation and proper URL structure for SEO.
```

The project restructures around Next.js pages with `getStaticProps`:

```typescript
// pages/products/[slug].tsx
export async function getStaticProps({ params }) {
  const product = await getProductBySlug(params.slug);
  return {
    props: { product },
    revalidate: 86400, // ISR: regenerate every 24 hours
  };
}

export async function getStaticPaths() {
  const products = await getAllProducts();
  return {
    paths: products.map(p => ({ params: { slug: p.slug } })),
    fallback: 'blocking', // New products SSR on first request, then cache
  };
}
```

Product pages use Incremental Static Regeneration -- pre-rendered at build time but refreshed every 24 hours, with on-demand revalidation via webhook for urgent content changes. Blog posts generate at build time with automatic sitemap.xml and RSS feed creation.

SEO optimization covers all the gaps the audit found: dynamic meta tags (title, description, keywords per page), Open Graph and Twitter Card tags for social sharing, canonical URLs to prevent duplicate content, and JSON-LD structured data (Organization, Product, Article schemas) for rich snippets in search results.

The Next.js Image component handles automatic WebP/AVIF conversion, responsive image sizing, lazy loading, and blur placeholders. Combined with critical CSS inlining and intelligent link prefetching, the JavaScript bundle drops from 847 KB to 156 KB through automatic code splitting and tree shaking.

### Step 3: Implement SSR for Dynamic Pages and Optimize Core Web Vitals

```text
Set up server-side rendering for dynamic pages like pricing calculator and
demo forms. Implement advanced performance optimizations to pass all Core
Web Vitals: optimize LCP, reduce CLS, minimize FID. Include edge caching
and progressive enhancement.
```

Dynamic pages use `getServerSideProps` with aggressive caching -- the pricing calculator caches for 5 minutes at the edge, demo request forms include A/B testing variants, and the user dashboard renders personalized content server-side.

Core Web Vitals optimization targets each metric individually:

**LCP: 7.1s to 1.2s** -- hero image optimization (2.1 MB to 387 KB via WebP), critical CSS inlining for above-the-fold content, font preloading before layout, and server-rendered HTML visible immediately instead of waiting for JavaScript.

**FID: 340ms to 45ms** -- JavaScript bundle reduction from 847 KB to 156 KB, per-page code splitting so each page loads only what it needs, third-party scripts deferred, heavy calculations moved to Web Workers.

**CLS: 0.23 to 0.02** -- explicit width/height on all images to prevent layout jumps, `font-display: swap` to prevent Flash of Invisible Text, reserved space for dynamic content, and animations restricted to `transform` and `opacity` (no layout-triggering properties).

Progressive enhancement ensures core content works without JavaScript. Hydration adds interactivity after the initial render. Service workers cache critical pages for offline access. Skeleton screens and error boundaries provide graceful degradation.

### Step 4: Deploy and Measure SEO Improvements

```text
Set up production deployment with Docker containers, implement proper caching
headers, and measure SEO performance improvements. Include A/B testing to
measure conversion rate improvements.
```

The production stack runs behind nginx with optimized caching headers: static assets get `max-age=31536000, immutable`, HTML pages use `s-maxage=86400` with `stale-while-revalidate`, and API routes cache based on data freshness. Brotli compression achieves 73% average file size reduction. CloudFront distributes content across 25+ global edge locations.

The before/after numbers after 90 days tell the story:

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Performance Score (mobile) | 31/100 | 96/100 | +209% |
| Largest Contentful Paint | 7.1s | 1.2s | -83% |
| Pages indexed by Google | 23% | 91% | +297% |
| Average search position | Page 3.4 | Page 1.8 | +94% |
| Bounce rate | 73% | 34% | -53% |
| Conversion rate | 3.1% | 7.9% | +155% |
| Mobile conversion rate | 1.8% | 6.2% | +244% |

An A/B test running the old CSR version against the new SSR/SSG version for 30 days shows 3.1% versus 7.9% conversion at 99.7% statistical confidence.

## Real-World Example

A B2B marketing automation platform was losing prospects before they could even see the product. Their React SPA took 8.3 seconds to show content on mobile, causing a 78% bounce rate and devastating inbound lead generation. Despite $85K annually on content marketing and SEO, organic traffic declined 12% quarter-over-quarter. The crisis point: their biggest competitor launched a faster site and jumped 2 positions for primary keywords, stealing an estimated $180K in annual contract value.

Weeks 1-2 focused on analysis: an 847 KB JavaScript bundle, 4.8s FCP, only 31% of pages indexed by Google. 38 pages suitable for SSG, 9 requiring SSR. Weeks 3-4 converted React components to Next.js pages with `getStaticProps`, added automatic image optimization and responsive images, and implemented proper meta tags and schema markup. Weeks 5-6 optimized Core Web Vitals through code splitting (82% bundle reduction), ISR for semi-static content, and edge caching.

After 120 days: PageSpeed score 28/100 to 94/100. All Core Web Vitals passing. Organic search traffic up 203%. Average search position improved from page 3.7 to page 1.4. Mobile conversion rate jumped from 1.9% to 8.3%. The migration added $67K in monthly recurring revenue from organic traffic alone.

The sales team noticed the difference immediately -- prospects stopped mentioning website speed as a concern and started complimenting it instead. Six months after the migration, they acquired two smaller competitors who cited the superior web experience as a factor in choosing their platform for acquisition. What started as a technical SEO fix became a measurable competitive advantage. The hosting costs actually decreased despite the better performance -- static generation means most pages are served from CDN cache at pennies per million requests, compared to the old setup where every page load required a full client-side render with 847 KB of JavaScript.
