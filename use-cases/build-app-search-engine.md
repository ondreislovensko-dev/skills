---
title: "Build and Optimize a Search Engine for Your App"
slug: build-app-search-engine
description: "Add fast, typo-tolerant, faceted search to your application using Elasticsearch or Algolia — from index design to relevance tuning."
skills: [search-engine-setup, docker-helper, data-analysis]
category: development
tags: [search, elasticsearch, algolia, full-text-search, relevance-tuning]
---

# Build and Optimize a Search Engine for Your App

## The Problem

Your app's search is a SQL `LIKE '%query%'` on the product name column. It misses typos, ignores synonyms, returns results in arbitrary order, and takes 3 seconds on 500K rows. A user types "wirless keyboard" and gets zero results. Another types "laptop stand" and the first result is a laptop bag. Your support team fields "I can't find X" tickets daily, and the analytics show search-driven conversions are half what they should be — because the search bar is effectively broken for anyone who can't spell perfectly or doesn't use the exact product name.

Setting up Elasticsearch feels like deploying a second database. Algolia's pricing is opaque at scale. The gap between a `LIKE` query and production-grade search feels enormous, so the team keeps patching the SQL approach with more ILIKE conditions and regex hacks that make it slower without making it smarter.

## The Solution

Using the **search-engine-setup**, **docker-helper**, and **data-analysis** skills, the workflow designs a search index tailored to your data with custom analyzers for typo tolerance, builds a sync pipeline from PostgreSQL that keeps the index fresh within 500ms, implements a search API with faceting and highlighting, adds autocomplete with "did you mean" suggestions, and tunes relevance using real user query logs. The whole stack goes from zero to sub-50ms search in an afternoon.

## Step-by-Step Walkthrough

### Step 1: Design the Search Index

Start with your data shape and search requirements:

```text
I have a products table with 500K rows. Columns: id, name, description, category, brand, price_cents, rating, in_stock, created_at. Design an Elasticsearch index mapping optimized for: full-text search on name and description with typo tolerance, exact filtering on category and brand, range filtering on price and rating, and boosting in-stock items. Include a custom analyzer for handling common misspellings.
```

The index mapping treats each field according to how users actually search:

```json
{
  "mappings": {
    "properties": {
      "name":        { "type": "text", "analyzer": "product_analyzer", "boost": 3.0 },
      "description": { "type": "text", "analyzer": "product_analyzer" },
      "category":    { "type": "keyword" },
      "brand":       { "type": "keyword" },
      "price_cents": { "type": "integer" },
      "rating":      { "type": "float" },
      "in_stock":    { "type": "boolean" },
      "created_at":  { "type": "date" },
      "suggest":     { "type": "completion" }
    }
  },
  "settings": {
    "analysis": {
      "analyzer": {
        "product_analyzer": {
          "tokenizer": "standard",
          "filter": ["lowercase", "product_synonyms", "edge_ngram_filter"]
        }
      },
      "filter": {
        "product_synonyms": {
          "type": "synonym",
          "synonyms": ["laptop, notebook", "phone, mobile, cell"]
        },
        "edge_ngram_filter": {
          "type": "edge_ngram", "min_gram": 3, "max_gram": 15
        }
      }
    }
  }
}
```

The `name` field gets a 3x boost because users searching "wireless keyboard" expect name matches to rank above products that merely mention "keyboard" in the description. The `product_analyzer` chains synonym expansion with edge n-grams, so "wirless" matches "wireless" and typing "key" already starts matching "keyboard." The `suggest` field powers autocomplete separately from full-text search — different use cases, different data structures, different performance characteristics.

The `keyword` type on `category` and `brand` means exact-match filtering without text analysis overhead. Users don't fuzzy-search for a brand; they click a facet.

### Step 2: Build the Sync Pipeline

The search index is only as good as its freshness. A product marked out-of-stock in PostgreSQL but still showing as available in search results is worse than no search at all:

```text
Create a sync service that keeps Elasticsearch in sync with PostgreSQL. On app boot, do a full re-index of all products. After that, listen to database change events (using pg_notify or polling updated_at) and update individual documents. Handle deletions by tracking soft-deleted records. Add a CLI command to trigger a full re-index manually.
```

The sync service handles three scenarios: full re-index on boot using the bulk API for speed (500K documents in about 90 seconds), incremental updates via `pg_notify` within 500ms of a database change, and soft-delete tracking so removed products don't linger in search results. A manual `reindex --full` command exists for emergencies or schema changes.

The incremental sync is the critical piece. When a product goes out of stock, the search index reflects it in under a second — not on the next full re-index, which might be hours away. Without incremental sync, users find products through search, click through, and see "Out of Stock" — a frustrating experience that erodes trust in the search results.

The `reindex --full` command serves as a safety net: if the incremental sync drifts (a missed `pg_notify`, a failed bulk update), a full re-index rebuilds everything from source. Running it weekly during off-hours provides peace of mind.

### Step 3: Implement the Search API

```text
Build a search endpoint at GET /api/search?q=wireless+keyboard&category=electronics&min_price=2000&max_price=10000&sort=relevance. Support: full-text query with fuzziness auto, faceted filters (category, brand, price range, rating, in_stock), pagination with cursor-based approach, and highlight matching terms in results. Return total count, facet counts, and highlighted snippets.
```

The endpoint combines full-text relevance scoring with structured filters in a single query. Facet counts update dynamically — selecting "Electronics" shows how many results exist per brand within that category, so users can drill down without hitting dead ends. Highlighted snippets show users exactly why a result matched, with matching terms wrapped in `<mark>` tags. Cursor-based pagination means consistent results even when the index is being updated mid-browse.

An in-stock boost ensures available products rank above out-of-stock ones, but out-of-stock products still appear (with a label) rather than disappearing entirely — because a user searching for a specific item wants to know it exists even if it's temporarily unavailable. Hiding out-of-stock products makes search results feel broken: "I know you sell this, why can't I find it?"

The response includes facet counts that dynamically update: after selecting "Electronics," the brand facet shows `Apple (142)`, `Samsung (98)`, `Sony (67)` — only counting products within the selected category. This lets users drill down without hitting dead ends.

### Step 4: Add Autocomplete and "Did You Mean"

```text
Add a typeahead endpoint at GET /api/search/suggest?q=wir that returns the top 5 completion suggestions from product names as the user types. Use Elasticsearch's completion suggester. Also add a "did you mean" feature using the phrase suggester for queries that return few results.
```

Autocomplete fires after 2 characters with sub-50ms response time, using the `completion` field that was designed for exactly this purpose. The suggestions come from actual product names, weighted by popularity, so "wir" suggests "Wireless Keyboard" before "Wire Stripper" if keyboards sell more.

When a full search returns fewer than 3 results, the phrase suggester kicks in — "wirless keybord" triggers a "Did you mean: wireless keyboard?" banner with a one-click correction link. This catches the queries that edge n-grams alone can't fix: severe misspellings, word transpositions, and queries in a different language.

### Step 5: Tune Relevance with Real Query Data

This is where search goes from functional to good. Building the index gets you 80% of the way; tuning relevance gets the last 20% that users actually feel:

```text
I have a log of the 200 most common search queries and their click-through rates in search_queries.csv (columns: query, result_count, ctr, avg_position_clicked). Analyze which queries perform poorly (low CTR or zero results). Suggest specific tuning actions: synonym additions, boost adjustments, or missing data fixes. Output a priority-ranked list of improvements.
```

The analysis breaks down into actionable categories:

**Zero-result queries (17 queries):**
- "wirless keyboard" — add synonym pair: wireless, wirless
- "usb-c dongle" — hyphenated terms split incorrectly, add `char_filter`
- "gift under 50" — needs price-aware query parsing, not just text matching

**Low CTR queries (below 5%, 23 queries):**
- "laptop stand" (CTR 2.1%) — top result is a laptop bag because "laptop" matches; boost exact name matches over partial matches
- "blue headphones" (CTR 3.4%) — color isn't a structured field, so "blue" only matches if it appears in the description; extract color into its own field

**Priority fixes ranked by impact:**
1. Add 12 synonym pairs for common misspellings — fixes 14 zero-result queries
2. Add `char_filter` for hyphens and special characters — fixes 3 zero-result queries
3. Increase name field boost from 3.0 to 5.0 — improves 8 low-CTR queries where description matches outrank name matches

Each fix has a measurable expected impact. Twelve synonym pairs alone eliminate 14 dead-end searches — queries where users were ready to buy but the search bar told them the product doesn't exist.

## Real-World Example

A senior developer at an online marketplace with 500K product listings is drowning in "I can't find X" support tickets. The current search is a PostgreSQL `ILIKE` query that averages 2.8 seconds and returns nothing for common misspellings. One developer tried adding `OR` clauses for common typos, which made the query 4 seconds and still missed most variations.

He starts with the index design — a custom analyzer with synonyms and edge n-grams handles typos and partial matches out of the box. The sync pipeline keeps Elasticsearch within 500ms of every database change. The search API handles full-text queries with faceted filters and returns highlighted results in 40ms — a 70x speedup over the SQL approach. Autocomplete suggestions appear after 2 characters with sub-50ms latency.

Query analysis of the 200 most common searches reveals 17 zero-result queries and 23 low-CTR queries, each with a specific fix. After deploying, search-driven conversion rate increases 34% and "can't find product" support tickets drop 89%. The `LIKE` query is gone for good, and so are the regex hacks that were making it worse.
