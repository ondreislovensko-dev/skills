---
title: "Test AI Prompts Systematically Before Shipping to Production"
slug: test-ai-prompts-systematically
description: "Design evaluation rubrics, build test suites, and compare prompt variants to find the best-performing AI instructions."
skills: [prompt-tester, data-analysis]
category: data-ai
tags: [prompt-engineering, llm, evaluation, ai-agents, testing]
---

# Test AI Prompts Systematically Before Shipping to Production

## The Problem

Your team ships an AI feature — a support ticket classifier, a document summarizer, an email drafter — and the prompt was written by one engineer who tested it on three examples that happened to work. In production, it misclassifies edge cases, hallucinates details, and the output format breaks downstream parsing. Prompt changes are deployed by vibes: "this version feels better." There's no test suite, no evaluation rubric, no way to know if a change improved or regressed quality.

This is how most teams ship prompts. And it works fine until the first production incident where the AI confidently extracts a wrong invoice amount or classifies a billing complaint as a feature request.

## The Solution

Use the **prompt-tester** skill to bring engineering rigor to prompt development. Define what good output looks like, build test cases covering normal and edge scenarios, run multiple prompt variants, and compare results with metrics. Combine with **data-analysis** to analyze patterns in failures and measure improvement over iterations.

## Step-by-Step Walkthrough

### Step 1: Define Your Evaluation Rubric

```text
I'm building an AI feature that extracts invoice data from emails. Help me
define evaluation criteria for the extraction prompt.
```

Before testing anything, you need to define what "correct" means. For an invoice extractor, the rubric covers five criteria:

| Criterion | Weight | Pass Condition |
|-----------|--------|----------------|
| Field accuracy | 40% | All 6 fields correct (vendor, amount, date, invoice number, due date, line items) |
| Partial extraction | 20% | At least 4 of 6 fields correct |
| Format validity | 15% | Output is valid JSON matching the expected schema |
| No hallucination | 15% | No invented fields or values |
| Graceful failure | 10% | Returns null fields instead of guessing when data is missing |

The weighting matters. Field accuracy is worth 40% because wrong data is worse than missing data. Hallucination gets 15% because a confidently wrong invoice amount causes real financial problems. Graceful failure gets 10% because silently returning null is always better than guessing.

### Step 2: Build a Test Suite

```text
Create 10 test cases for the invoice extractor. Include normal invoices,
edge cases like partial data, and adversarial inputs.
```

Ten test cases cover three categories with increasing difficulty:

**Normal cases (5):**
- TC-01: Standard invoice email with all fields present
- TC-02: Invoice as PDF attachment (extraction from body text only)
- TC-03: Invoice in HTML table format
- TC-04: Multi-line-item invoice with subtotals
- TC-05: International invoice (EUR currency, DD/MM/YYYY date format)

**Edge cases (3):**
- TC-06: Email mentions an invoice but is actually a receipt (different document type)
- TC-07: Two invoices in one email thread
- TC-08: Invoice with missing due date

**Adversarial inputs (2):**
- TC-09: Marketing email with dollar amounts that looks like an invoice but isn't
- TC-10: Empty email body with subject line "Invoice #1234"

Each test case includes the input email and the expected output JSON. The adversarial cases are where most prompts break — they test whether the model knows to say "this isn't an invoice" instead of extracting data from noise.

### Step 3: Test Prompt Variants

```text
Here are two versions of my extraction prompt. Run both against all 10 test
cases and compare.
```

Both variants run against all 10 test cases. The comparison is immediate:

| Metric | Variant A | Variant B |
|--------|-----------|-----------|
| Full accuracy (6/6 fields) | 60% | 80% |
| Partial accuracy (4+/6 fields) | 80% | 90% |
| Format valid JSON | 100% | 100% |
| Hallucinated values | 2 cases | 0 cases |
| Graceful failure (of 3 edge cases) | 1/3 | 3/3 |

The key differences tell the story:
- Variant B correctly identifies the marketing email (TC-09) as "not an invoice" and returns null. Variant A extracts a fake invoice from the marketing copy.
- Variant A invents a due date for TC-08 where none exists — a hallucination that could cause a real payment error.
- Variant B correctly extracts both invoices from TC-07 (two invoices in one thread).

Variant B wins: 80% accuracy with zero hallucinations versus 60% with two hallucinations.

### Step 4: Iterate on Failures

```text
Variant B failed on TC-05 (international format) and TC-10 (empty body).
Help me fix the prompt for these cases.
```

Failure analysis reveals two specific gaps in the prompt:

**TC-05 (international format):** The prompt doesn't mention that dates might be in DD/MM/YYYY format, so the model interprets "05/03/2026" as May 3rd instead of March 5th. The fix: add explicit instructions for date format handling — "Dates may appear in DD/MM/YYYY, MM/DD/YYYY, or written format. Parse based on context and locale."

**TC-10 (empty body):** The prompt says "extract from the email" but doesn't mention the subject line as a data source. The fix: add "Check both email body and subject line for invoice data."

Both fixes are targeted — they address the specific failure without changing what already works. A rerun of just the two failed cases confirms both now pass.

### Step 5: Document the Final Prompt

```text
Create a prompt spec document with the final version, its test results,
and when to re-evaluate.
```

The prompt spec becomes the source of truth for the production prompt:

**Invoice Email Extractor v2.1**
- Last tested: 2026-02-17
- Model: claude-sonnet-4-20250514
- Test suite: 10 cases, 90% full accuracy, 100% partial accuracy, 0 hallucinations

**Known limitations:**
- Scanned PDF invoices (no OCR in email body)
- Invoices in languages other than English and Spanish

**Re-evaluate when:**
- Switching model versions (accuracy may shift)
- Adding new invoice formats from customer requests
- Accuracy drops below 85% in production monitoring

The test suite lives alongside the prompt in version control. Every prompt change triggers a re-run before deployment. No more shipping by vibes.

## Real-World Example

Amir is an ML engineer at a legal tech startup. They built an AI feature that extracts key clauses from contracts — termination terms, liability caps, payment schedules. The initial prompt worked on their 5 sample contracts but failed badly on real customer documents with unusual formatting.

He builds an eval suite with 15 test cases from different contract types: SaaS agreements, NDAs, consulting contracts, and international contracts. The current prompt scores 53% accuracy — much worse than the team assumed. Failure analysis shows the pattern: most misses come from contracts with nested clauses and cross-references, a structure the prompt doesn't account for.

Three prompt iterations follow, each targeting the specific failure patterns from the previous run. Version 2 handles nested clauses. Version 3 resolves cross-reference ambiguity. The final version scores 88% accuracy with zero hallucinations on the test suite.

Amir adds the test suite to CI — every prompt change now runs against the eval before deployment. Time invested: 2 hours. Result: prompt accuracy went from 53% to 88%, and every future change is tested before shipping.
