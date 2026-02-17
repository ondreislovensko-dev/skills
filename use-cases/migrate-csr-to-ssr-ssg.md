---
title: "Implement Server-Side Rendering Migration from CSR to SSR/SSG"
slug: migrate-csr-to-ssr-ssg
description: "Incrementally migrate a client-side rendered React app to Next.js with SSR and SSG for better SEO, performance, and Core Web Vitals."
skills: [ssr-migration, frontend-design, docker-helper]
category: development
tags: [ssr, ssg, nextjs, react, seo, performance]
---

# Implement Server-Side Rendering Migration from CSR to SSR/SSG

## The Problem

Your React single-page application renders everything in the browser. Search engines see a blank page with a `<div id="root"></div>` — your product pages don't appear in search results despite great content. Core Web Vitals are poor: Largest Contentful Paint sits at 4.2 seconds because the browser has to download JavaScript, execute it, fetch data from the API, then render. Users on slower connections see a white screen for 3-5 seconds before anything appears. Social media link previews show your app's generic meta tags instead of page-specific content. The marketing team is frustrated that blog posts and landing pages are invisible to search crawlers, and the performance team's attempts to optimize bundle size have hit diminishing returns — the fundamental architecture is the bottleneck.

## The Solution

Use the **ssr-migration** skill to incrementally migrate routes from client-side rendering to server-side rendering and static site generation using Next.js App Router. Use **frontend-design** to ensure components work correctly in both server and client contexts, and **docker-helper** for the production SSR deployment setup. The key: migrate one route at a time, starting with the highest-SEO-value pages, without rewriting the entire application.

```bash
npx terminal-skills install ssr-migration
npx terminal-skills install frontend-design
npx terminal-skills install docker-helper
```

## Step-by-Step Walkthrough

### 1. Audit the application and plan the migration

```
Audit my React SPA for SSR readiness. The app has these routes: homepage, product
listing, product detail (200 products), blog (80 posts), user dashboard, settings,
and admin panel. Identify which routes should be SSG, SSR, or stay CSR, and flag
any code patterns that will break with server rendering.
```

The agent scans the codebase for SSR-incompatible patterns: finds 8 components using `window` directly, 3 libraries that only work in the browser (a charting library, a rich text editor, a map component), and 2 instances of `localStorage` access at module level. It produces a migration plan: SSG for homepage, blog, and product pages (highest SEO value, content changes infrequently); SSR for product listing and search (dynamic but SEO-important); CSR for dashboard, settings, and admin (authenticated, no SEO need).

### 2. Set up Next.js and migrate the first SSG pages

```
Initialize Next.js App Router in my existing project. Migrate the blog listing
and blog post pages first — they're the highest SEO priority. Use static site
generation with incremental static regeneration (revalidate every 30 minutes).
Keep the existing React components, just change the data fetching pattern.
```

The agent creates the Next.js configuration alongside the existing React setup, moves the blog components into `app/blog/page.tsx` and `app/blog/[slug]/page.tsx` as Server Components. Data fetching moves from `useEffect` + loading spinner to `async/await` in the Server Component. It adds `generateStaticParams` to pre-render all 80 blog posts at build time and sets `revalidate: 1800` for ISR. The existing blog components are reused — only the data fetching wrapper changes.

### 3. Handle browser-only components and hydration

```
Three of my components use browser-only libraries: ProductChart (chart.js),
RichEditor (a WYSIWYG editor), and LocationMap (mapbox). These can't run on
the server. Also fix the hydration mismatch in my Navbar component that shows
the current user — it renders differently on server vs client.
```

The agent wraps all three browser-only components with `next/dynamic` using `{ ssr: false }` and adds loading placeholders. For the Navbar, it splits into a Server Component shell (static navigation links) and a Client Component for the user menu that reads auth state via `useEffect` on mount, preventing the hydration mismatch. It adds `suppressHydrationWarning` only for the timestamp display in the footer — a legitimate use case.

### 4. Migrate product pages and configure deployment

```
Migrate the product listing (SSR) and product detail pages (SSG with ISR).
Product detail pages should be statically generated for all 200 products and
revalidate when the product is updated via a webhook. Also create a production
Dockerfile for the SSR deployment.
```

The agent creates `app/products/page.tsx` as an SSR Server Component that fetches with `{ cache: 'no-store' }` for always-fresh listings. Product detail pages use `generateStaticParams` for all 200 products and a `revalidatePath` API route triggered by a webhook on product update. It generates a multi-stage Dockerfile using Next.js standalone output mode — the final image is 85MB instead of 500MB+ with a full `node_modules`. It adds a `docker-compose.production.yml` with the Next.js container, health checks, and a reverse proxy configuration.

## Real-World Example

Tomoko, a frontend lead at a growing e-commerce startup, reviews the quarterly SEO report: organic traffic has stagnated despite publishing 80 blog posts and having 200 well-described products. The technical SEO audit reveals the issue — search crawlers see an empty page because all content is rendered client-side. The LCP score is 4.2 seconds, and social media shares show generic placeholder images instead of product photos. A full rewrite to Next.js was estimated at 3 months, which the team can't afford.

1. Tomoko asks the agent to audit the React SPA and create an incremental migration plan
2. The agent identifies the 5 highest-impact routes for SSG/SSR and flags 11 code patterns to fix
3. She starts with the blog — the agent migrates blog listing and post pages to SSG with ISR in one session
4. After deploying the blog migration, blog posts appear in search results within 48 hours — organic traffic to blog pages increases 340% in the first month
5. She migrates product pages next — SSG with webhook-triggered revalidation — and LCP drops from 4.2s to 1.1s
6. The dashboard and admin panel stay as CSR, wrapped in a route group — zero effort, no regression

The full migration takes 3 weeks of incremental work, not 3 months. Each route is deployed independently, and at no point does the existing application break.

## Related Skills

- [ssr-migration](../skills/ssr-migration/) — Core SSR/SSG migration patterns, hydration fixes, and deployment config
- [frontend-design](../skills/frontend-design/) — Ensure components work correctly across server and client contexts
- [docker-helper](../skills/docker-helper/) — Build optimized containers for SSR production deployment
