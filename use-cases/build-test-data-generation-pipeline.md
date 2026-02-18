---
title: "Build an Automated Test Data Generation Pipeline with AI"
slug: build-test-data-generation-pipeline
description: "Generate realistic, schema-aware test data at scale for development, staging, and automated testing environments."
skills: [coding-agent, test-generator, data-analysis]
category: development
tags: [testing, test-data, automation, development, data-generation]
---

# Build an Automated Test Data Generation Pipeline with AI

## The Problem

A 20-person SaaS startup runs integration tests against a staging database with 50 rows of hand-crafted test data. The data was written two years ago and no longer reflects real usage patterns — there are no edge cases, no unicode characters in names, no addresses outside the US, and no records that trigger the new subscription tiers added last quarter.

QA keeps finding bugs in production that never surface in staging because the test data doesn't cover the scenarios real users create. A customer in Tokyo with a name containing kanji? Never tested. A subscription that was downgraded mid-billing-cycle? Not in the dataset. Meanwhile, developers copy production data for local testing, which is a compliance nightmare since it contains real customer PII.

The test data problem has two sides: too little variety to catch bugs, and too much risk when developers reach for the easy fix of using production dumps. The compliance team has asked three times for production data to be removed from developer machines, and three times it has crept back because there is no viable alternative.

## The Solution

Using the **coding-agent**, **test-generator**, and **data-analysis** skills, the agent analyzes the existing schema, builds data factories that understand relationships and constraints, generates thousands of realistic records with international names and edge cases, and creates scenario-specific datasets for targeted testing.

## Step-by-Step Walkthrough

### Step 1: Analyze the Schema and Relationships

```text
Analyze the database schema in ./prisma/schema.prisma. Map all tables,
relationships, constraints, and enums. Identify which fields need
realistic data (emails, addresses, phone numbers) versus which are
system-generated (UUIDs, timestamps).
```

The schema analysis maps the full data model:

- **24 tables**, **156 columns** across 5 core entities: User, Organization, Project, Task, Subscription
- **31 foreign keys** and **4 many-to-many relationships** via junction tables
- **12 unique indexes**, **8 check constraints**, and **3 custom enums**

Every column gets classified: fields like `name`, `email`, `phone`, and `address` need realistic, internationalized values. Fields like `id`, `created_at`, and `updated_at` are system-generated. Foreign keys need to reference records that actually exist, in the right order.

### Step 2: Generate Data Factories

```text
Create data factory functions for each entity that generate realistic data.
Include: international names and addresses (at least US, EU, Japan, Brazil),
edge cases (very long names, special characters, emoji in text fields),
and valid relational integrity across all foreign keys. Generate 10,000
users across 500 organizations.
```

The factories produce data that looks like it came from real users, not a test harness:

```typescript
// factories/user.factory.ts

const UserFactory = {
  // International name variants — not just "John Smith" over and over
  names: [
    { first: "Jose", last: "Garcia-Lopez" },      // Spanish compound surname
    { first: "Yuki", last: "Tanaka" },             // Japanese
    { first: "Muller", last: "Braun" },            // German (with umlaut variant)
    { first: "Priya", last: "O'Brien-Sharma" },    // Hyphenated multicultural
    // ... 200+ name templates across 12 locales
  ],

  // Edge cases that break naive string handling
  edgeCases: [
    { first: "Li", last: "W" },                    // Minimum-length names
    { first: "A".repeat(100), last: "Test" },      // Maximum-length boundary
    { first: "Anna-Maria", last: "von der Luhe" }, // Particles and hyphens
  ],

  // 12 timezone variants, valid email formats, real phone patterns
  generate: (overrides?) => ({ /* ... */ }),
};
```

Each factory respects constraints: unique indexes never collide, foreign keys reference existing records, enums use valid values, and nullable fields are sometimes null (not always filled). The factories seed in dependency order — Organizations before Users, Users before Projects — so foreign keys never point to missing records.

Seeding 10,000 users across 500 organizations takes 47 seconds. All foreign key and unique constraints pass validation. The seed script logs a summary of what was created — useful for debugging when a test expects a specific record count.

### Step 3: Cover the Edge Cases That Catch Real Bugs

The generated data includes the cases that hand-crafted test data always misses:

- **Names with diacritics:** Jose, Muller, Tanaka Yuki, O'Brien
- **Emoji in text fields:** task descriptions with unicode characters
- **Zero-length optional fields:** nullable columns that are actually null
- **Boundary dates:** leap year (Feb 29), DST transitions, year-end rollovers
- **Max-length strings:** fields filled to exactly the column limit
- **Timezone extremes:** UTC+13 (Samoa), UTC-12 (Baker Island)

These are the exact patterns that caused three production bugs last quarter: a name truncation issue with Japanese characters, a timezone calculation error for UTC+13, and a date formatting crash on leap year birthdays.

### Step 4: Create Scenario-Specific Datasets

```text
Generate a focused dataset for testing the billing system: 20 organizations
with subscriptions in every state — active, trial expiring tomorrow, trial
expired, payment failed, cancelled, downgraded mid-cycle, upgraded mid-cycle,
and annual renewal due today.
```

The billing test dataset exercises every subscription edge case:

| State | Count | What It Tests |
|---|---|---|
| Pro monthly ($49/mo), various usage levels | 5 orgs | Normal billing flow |
| Enterprise annual ($499/mo), approaching renewal | 3 orgs | Annual renewal logic |
| Starter free tier, approaching usage limit | 2 orgs | Upgrade prompts |
| Trial expiring tomorrow | 2 orgs | Conversion email trigger |
| Trial expired 3 days ago | 1 org | Account lockout flow |
| Mid-trial with heavy usage | 1 org | Conversion candidate scoring |
| Failed payment, retry scheduled | 2 orgs | Payment retry logic |
| Expired credit card | 1 org | Card update notification |
| Downgraded mid-cycle (prorated credit) | 1 org | Proration calculation |
| Upgraded mid-cycle (prorated charge) | 1 org | Proration calculation |
| Cancelled with 15 days remaining | 1 org | Cancellation grace period |

All amounts, dates, and Stripe-compatible payment method tokens are included — the dataset is ready to use with the Stripe test API without any manual setup.

Running the existing billing test suite against this dataset immediately reveals a race condition in the payment retry logic that never surfaced with the old 50-row dataset. The race condition only triggers when two subscriptions in the same organization change state simultaneously, a scenario that the old hand-crafted data never created because every organization had exactly one subscription.

### Step 5: Wire It Into CI

The data generation pipeline plugs directly into CI — every test run gets fresh, realistic data instead of stale fixtures:

```bash
# In the CI pipeline
npx prisma migrate reset --force    # Clean slate
npx ts-node scripts/seed.ts         # Generate 10,000 users, 500 orgs
npx jest --runInBand                 # Run tests against fresh data
```

The seed script is idempotent and deterministic when given a seed value, so test failures are reproducible. Without a seed, it randomizes — catching different edge cases on each run.

This combination is powerful: deterministic seeds for debugging ("this test failed with seed 42, here's how to reproduce it") and random seeds in the nightly build to surface edge cases that a fixed dataset would miss. Some teams run both: a fixed seed in the PR pipeline for fast, reproducible checks, and a random seed in the nightly build for broader coverage.

## Real-World Example

Lena, the QA lead, runs the existing test suite against the new generated data on day one. Three bugs surface immediately: a name truncation issue with Japanese characters that silently corrupted display names, a timezone calculation error for UTC+13 that shifted scheduled tasks by a full day, and a billing edge case where mid-cycle plan changes produced negative invoice amounts.

All three bugs existed in production. Two of them had generated customer support tickets that the team attributed to "edge cases" without realizing the test suite was structurally incapable of catching them. None of them appeared with the old 50-row test dataset because it only contained ASCII names, US timezones, and simple subscription states.

The team adds the data generation pipeline to CI. Every test run gets 10,000 fresh records with randomized edge cases. Production database copies are deleted from developer machines, eliminating the PII compliance risk that kept the security team up at night. Over the next quarter, the bug escape rate — bugs found in production that should have been caught in testing — drops by 60%. The security team signs off on the PII compliance audit for the first time without exceptions. And the QA team finally stops hearing "works on my machine" from developers, because everyone tests against the same generated dataset instead of their own hand-crafted fixtures.
