---
title: Build a Web Crawling Pipeline with Crawlee and Firecrawl
slug: build-crawl-pipeline-with-crawlee-and-firecrawl
description: >-
  Build a production web crawling pipeline that extracts structured data from
  websites, handles JavaScript-rendered pages, respects rate limits, stores
  results in a database, and feeds data into AI applications.
skills:
  - crawlee
  - firecrawl
  - puppeteer
  - redis
  - drizzle-orm
category: data
tags:
  - web-scraping
  - data-extraction
  - crawling
  - ai
  - automation
---

# Build a Web Crawling Pipeline with Crawlee and Firecrawl

Nina is building a competitive intelligence tool. She needs to crawl competitor websites daily — extract pricing pages, product features, blog posts, and changelog entries. Some sites are static HTML, others are heavy SPAs that need JavaScript rendering. She needs structured data output, deduplication, rate limiting, and the ability to feed extracted content into an LLM for analysis.

## Step 1: Quick Extraction with Firecrawl

```typescript
// src/crawlers/firecrawl-extractor.ts
import FirecrawlApp from "@mendable/firecrawl-js";

const firecrawl = new FirecrawlApp({ apiKey: process.env.FIRECRAWL_API_KEY! });

export async function extractPricingPage(url: string) {
  const result = await firecrawl.scrapeUrl(url, {
    formats: ["markdown", "extract"],
    extract: {
      schema: {
        type: "object",
        properties: {
          plans: {
            type: "array",
            items: {
              type: "object",
              properties: {
                name: { type: "string" },
                price: { type: "string" },
                billing: { type: "string", enum: ["monthly", "yearly", "one-time"] },
                features: { type: "array", items: { type: "string" } },
                limits: { type: "string" },
              },
            },
          },
          hasFreeTier: { type: "boolean" },
          hasEnterprise: { type: "boolean" },
          lastUpdated: { type: "string" },
        },
      },
      prompt: "Extract all pricing plans with their features, prices, and limits.",
    },
  });

  return result.extract;
}

// Crawl entire site and get all pages as markdown
export async function crawlSite(url: string, maxPages: number = 50) {
  const result = await firecrawl.crawlUrl(url, {
    limit: maxPages,
    scrapeOptions: {
      formats: ["markdown"],
      onlyMainContent: true,
    },
  });

  return result.data?.map((page) => ({
    url: page.metadata?.sourceURL,
    title: page.metadata?.title,
    content: page.markdown,
  }));
}
```

## Step 2: Custom Crawler with Crawlee for Complex Sites

```typescript
// src/crawlers/competitor-crawler.ts
import { PlaywrightCrawler, Dataset, RequestQueue } from "crawlee";

interface CompetitorData {
  url: string;
  type: "pricing" | "feature" | "blog" | "changelog";
  title: string;
  content: string;
  extractedAt: string;
}

export async function crawlCompetitor(baseUrl: string, competitor: string) {
  const requestQueue = await RequestQueue.open(`competitor-${competitor}`);

  await requestQueue.addRequest({ url: `${baseUrl}/pricing`, userData: { type: "pricing" } });
  await requestQueue.addRequest({ url: `${baseUrl}/features`, userData: { type: "feature" } });
  await requestQueue.addRequest({ url: `${baseUrl}/blog`, userData: { type: "blog" } });
  await requestQueue.addRequest({ url: `${baseUrl}/changelog`, userData: { type: "changelog" } });

  const crawler = new PlaywrightCrawler({
    requestQueue,
    maxConcurrency: 2,
    maxRequestsPerMinute: 20,
    requestHandlerTimeoutSecs: 60,
    navigationTimeoutSecs: 30,

    async requestHandler({ request, page, enqueueLinks, log }) {
      const type = request.userData.type as string;
      log.info(`Crawling [${type}]: ${request.url}`);

      // Wait for dynamic content to load
      await page.waitForLoadState("networkidle");

      const title = await page.title();
      const content = await page.evaluate(() => {
        const main = document.querySelector("main, article, [role='main'], .content");
        return (main || document.body).innerText;
      });

      await Dataset.pushData<CompetitorData>({
        url: request.url,
        type: type as CompetitorData["type"],
        title,
        content,
        extractedAt: new Date().toISOString(),
      });

      // Follow links on blog/changelog pages
      if (type === "blog" || type === "changelog") {
        await enqueueLinks({
          strategy: "same-domain",
          globs: type === "blog"
            ? [`${baseUrl}/blog/**`]
            : [`${baseUrl}/changelog/**`],
          userData: { type },
          transformRequestFunction: (req) => {
            req.userData.type = type;
            return req;
          },
        });
      }
    },

    failedRequestHandler({ request, log }) {
      log.error(`Failed: ${request.url}`);
    },
  });

  await crawler.run();
  return Dataset.getData();
}
```

## Step 3: Store and Deduplicate Results

```typescript
// src/storage/crawl-store.ts
import { db } from "../db";
import { crawlResults } from "../db/schema";
import { eq, and } from "drizzle-orm";
import { createHash } from "crypto";

export async function storeCrawlResult(data: {
  competitor: string;
  url: string;
  type: string;
  title: string;
  content: string;
}) {
  const contentHash = createHash("sha256").update(data.content).digest("hex");

  // Check if content has changed since last crawl
  const existing = await db.query.crawlResults.findFirst({
    where: and(
      eq(crawlResults.url, data.url),
      eq(crawlResults.competitor, data.competitor)
    ),
    orderBy: (t, { desc }) => [desc(t.crawledAt)],
  });

  if (existing && existing.contentHash === contentHash) {
    return { stored: false, reason: "unchanged" };
  }

  await db.insert(crawlResults).values({
    competitor: data.competitor,
    url: data.url,
    type: data.type,
    title: data.title,
    content: data.content,
    contentHash,
    crawledAt: new Date(),
    hasChanged: !!existing,
  });

  return { stored: true, changed: !!existing };
}
```

## Step 4: Feed into LLM for Analysis

```typescript
// src/analysis/competitor-analysis.ts
import Anthropic from "@anthropic-ai/sdk";
import { db } from "../db";
import { crawlResults } from "../db/schema";
import { eq, desc, and, gte } from "drizzle-orm";

const anthropic = new Anthropic();

export async function analyzeCompetitorChanges(competitor: string, sinceDays: number = 7) {
  const since = new Date(Date.now() - sinceDays * 86400000);

  const changes = await db.query.crawlResults.findMany({
    where: and(
      eq(crawlResults.competitor, competitor),
      eq(crawlResults.hasChanged, true),
      gte(crawlResults.crawledAt, since)
    ),
    orderBy: [desc(crawlResults.crawledAt)],
  });

  if (changes.length === 0) return { summary: "No changes detected", changes: [] };

  const response = await anthropic.messages.create({
    model: "claude-sonnet-4-20250514",
    max_tokens: 2000,
    messages: [{
      role: "user",
      content: `Analyze these competitor changes from the past ${sinceDays} days and provide strategic insights:\n\n${changes.map((c) => `## ${c.type}: ${c.title}\nURL: ${c.url}\n${c.content.slice(0, 2000)}`).join("\n\n---\n\n")}`,
    }],
  });

  return {
    summary: response.content[0].type === "text" ? response.content[0].text : "",
    changesCount: changes.length,
  };
}
```

## Summary

Nina runs her crawler daily via cron. Firecrawl handles quick extraction with structured output (pricing pages become JSON automatically). Crawlee handles JavaScript-heavy sites with Playwright, respecting rate limits and handling retries. Results are deduplicated by content hash — she only stores and gets alerted when something actually changes. The LLM analysis step turns raw crawled data into actionable competitive intelligence: "Competitor X dropped their Pro plan price by 20% and added three features from your roadmap."
