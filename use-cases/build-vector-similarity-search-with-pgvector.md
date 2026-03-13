---
title: Build Vector Similarity Search with pgvector
slug: build-vector-similarity-search-with-pgvector
description: >-
  Add semantic search to your app using pgvector in PostgreSQL — store
  embeddings, query by similarity, build hybrid search combining full-text
  and vector search, and power AI features without a separate vector database.
skills:
  - pgvector
  - drizzle-orm
  - neon
category: ai
tags:
  - vector-search
  - embeddings
  - ai
  - postgresql
  - semantic-search
---

# Build Vector Similarity Search with pgvector

Nadia's help center has 2,000 articles. Keyword search fails when users describe problems in natural language — searching "my app keeps crashing" doesn't find the article titled "Troubleshooting Application Stability Issues." She needs semantic search: understand the meaning, not just keywords. pgvector adds vector operations to PostgreSQL, so she stores embeddings alongside her existing data — no separate vector database to manage.

## Step 1: Enable pgvector

```sql
-- Enable the extension (works on Neon, Supabase, RDS, self-hosted)
CREATE EXTENSION IF NOT EXISTS vector;
```

```typescript
// src/db/schema.ts
import { pgTable, text, timestamp, uuid, index, integer } from "drizzle-orm/pg-core";
import { vector } from "drizzle-orm/pg-core"; // pgvector support in Drizzle

export const articles = pgTable("articles", {
  id: uuid("id").defaultRandom().primaryKey(),
  title: text("title").notNull(),
  content: text("content").notNull(),
  slug: text("slug").notNull().unique(),
  category: text("category").notNull(),
  embedding: vector("embedding", { dimensions: 1536 }),  // OpenAI text-embedding-3-small
  createdAt: timestamp("created_at").defaultNow().notNull(),
  updatedAt: timestamp("updated_at").defaultNow().notNull(),
}, (t) => [
  // HNSW index for fast approximate nearest neighbor search
  index("articles_embedding_idx").using("hnsw", t.embedding.op("vector_cosine_ops")),
]);
```

## Step 2: Generate and Store Embeddings

```typescript
// src/lib/embeddings.ts
import OpenAI from "openai";
import { db } from "../db";
import { articles } from "../db/schema";
import { eq, isNull } from "drizzle-orm";

const openai = new OpenAI();

export async function generateEmbedding(text: string): Promise<number[]> {
  const response = await openai.embeddings.create({
    model: "text-embedding-3-small",
    input: text,
  });
  return response.data[0].embedding;
}

// Index a single article
export async function indexArticle(articleId: string) {
  const article = await db.query.articles.findFirst({
    where: eq(articles.id, articleId),
  });
  if (!article) throw new Error("Article not found");

  // Combine title and content for richer embedding
  const textToEmbed = `${article.title}\n\n${article.content}`;
  const embedding = await generateEmbedding(textToEmbed);

  await db.update(articles)
    .set({ embedding })
    .where(eq(articles.id, articleId));
}

// Batch index all articles missing embeddings
export async function indexAllArticles() {
  const unindexed = await db.query.articles.findMany({
    where: isNull(articles.embedding),
  });

  console.log(`Indexing ${unindexed.length} articles...`);

  for (const article of unindexed) {
    await indexArticle(article.id);
    console.log(`  ✅ ${article.title}`);
    // Rate limit: OpenAI allows ~3000 RPM
    await new Promise((r) => setTimeout(r, 100));
  }
}
```

## Step 3: Semantic Search

```typescript
// src/lib/search.ts
import { db } from "../db";
import { articles } from "../db/schema";
import { sql, desc, and, ilike, or } from "drizzle-orm";
import { generateEmbedding } from "./embeddings";

interface SearchResult {
  id: string;
  title: string;
  content: string;
  category: string;
  similarity: number;
}

// Pure vector search — find semantically similar articles
export async function semanticSearch(query: string, limit = 10): Promise<SearchResult[]> {
  const queryEmbedding = await generateEmbedding(query);

  const results = await db
    .select({
      id: articles.id,
      title: articles.title,
      content: articles.content,
      category: articles.category,
      similarity: sql<number>`1 - (${articles.embedding} <=> ${JSON.stringify(queryEmbedding)}::vector)`,
    })
    .from(articles)
    .where(sql`${articles.embedding} IS NOT NULL`)
    .orderBy(sql`${articles.embedding} <=> ${JSON.stringify(queryEmbedding)}::vector`)
    .limit(limit);

  return results;
}

// Hybrid search — combine keyword + semantic for best results
export async function hybridSearch(query: string, limit = 10): Promise<SearchResult[]> {
  const queryEmbedding = await generateEmbedding(query);

  const results = await db
    .select({
      id: articles.id,
      title: articles.title,
      content: articles.content,
      category: articles.category,
      // Combine text rank and vector similarity
      similarity: sql<number>`
        (0.3 * ts_rank(to_tsvector('english', ${articles.title} || ' ' || ${articles.content}), plainto_tsquery('english', ${query})))
        +
        (0.7 * (1 - (${articles.embedding} <=> ${JSON.stringify(queryEmbedding)}::vector)))
      `,
    })
    .from(articles)
    .where(
      or(
        // Text match OR semantic similarity
        sql`to_tsvector('english', ${articles.title} || ' ' || ${articles.content}) @@ plainto_tsquery('english', ${query})`,
        sql`(${articles.embedding} <=> ${JSON.stringify(queryEmbedding)}::vector) < 0.5`
      )
    )
    .orderBy(desc(sql`
      (0.3 * ts_rank(to_tsvector('english', ${articles.title} || ' ' || ${articles.content}), plainto_tsquery('english', ${query})))
      +
      (0.7 * (1 - (${articles.embedding} <=> ${JSON.stringify(queryEmbedding)}::vector)))
    `))
    .limit(limit);

  return results;
}
```

## Step 4: RAG-Powered Answer Generation

```typescript
// src/lib/rag.ts
import OpenAI from "openai";
import { hybridSearch } from "./search";

const openai = new OpenAI();

export async function answerQuestion(question: string) {
  // Find relevant articles
  const results = await hybridSearch(question, 5);

  if (results.length === 0) {
    return { answer: "I couldn't find any relevant articles.", sources: [] };
  }

  // Build context from top results
  const context = results
    .map((r, i) => `[${i + 1}] ${r.title}\n${r.content.slice(0, 1000)}`)
    .join("\n\n---\n\n");

  const response = await openai.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      {
        role: "system",
        content: "Answer the user's question based on the provided help articles. Cite sources using [1], [2], etc. If the articles don't contain the answer, say so.",
      },
      {
        role: "user",
        content: `Question: ${question}\n\nRelevant articles:\n${context}`,
      },
    ],
    temperature: 0.3,
    max_tokens: 500,
  });

  return {
    answer: response.choices[0].message.content,
    sources: results.map((r) => ({ id: r.id, title: r.title, similarity: r.similarity })),
  };
}
```

## Step 5: API Endpoint

```typescript
// src/app/api/search/route.ts
import { NextRequest } from "next/server";
import { hybridSearch } from "@/lib/search";
import { answerQuestion } from "@/lib/rag";

export async function GET(req: NextRequest) {
  const query = req.nextUrl.searchParams.get("q");
  if (!query) return Response.json({ error: "Query required" }, { status: 400 });

  const mode = req.nextUrl.searchParams.get("mode") || "search";

  if (mode === "answer") {
    const result = await answerQuestion(query);
    return Response.json(result);
  }

  const results = await hybridSearch(query);
  return Response.json({ results });
}
```

## Summary

Nadia's help center search went from frustrating keyword matching to intelligent semantic understanding. "My app keeps crashing" now finds the stability troubleshooting article (0.89 similarity score). Hybrid search combines the precision of keyword matching ("error code 5012") with semantic understanding ("how do I export my data"). The RAG endpoint generates answers from article content with citations, reducing support tickets by 40%. All of this runs in her existing PostgreSQL database — pgvector adds vector operations natively, so there's no separate Pinecone or Weaviate to manage, pay for, and keep in sync.
