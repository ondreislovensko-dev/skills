---
name: lemon-squeezy
description: >-
  Assists with selling digital products, SaaS subscriptions, and software licenses using
  Lemon Squeezy as a Merchant of Record. Use when setting up checkout flows, webhook handling,
  license key validation, or subscription management with automatic global tax compliance.
  Trigger words: lemon squeezy, merchant of record, digital sales, license keys, subscriptions.
license: Apache-2.0
compatibility: "No special requirements"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: business
  tags: ["lemon-squeezy", "payments", "subscriptions", "merchant-of-record", "licensing"]
---

# Lemon Squeezy

## Overview

Lemon Squeezy is a Merchant of Record platform for selling digital products, SaaS subscriptions, and software licenses. It handles global tax compliance (VAT, GST, sales tax), payment processing, fraud prevention, and invoicing, allowing developers to focus on building the product rather than managing billing infrastructure.

## Instructions

- When setting up a product, create products and variants (tiers/plans) in the Lemon Squeezy dashboard with the appropriate pricing model: one-time, subscription, usage-based, or pay-what-you-want.
- When integrating checkout, use the hosted checkout URL or embed Lemon.js for an in-app checkout overlay, passing `checkout[custom][user_id]` to link purchases to your internal user model.
- When handling webhooks, verify signatures using `crypto.timingSafeEqual()` with HMAC-SHA256, then process events like `order_created`, `subscription_created`, and `subscription_payment_failed`.
- When managing subscriptions, use the REST API to check status (`GET /v1/subscriptions/{id}`), update plans, or pause/cancel, and direct customers to the hosted portal for self-service billing management.
- When implementing license keys, use the validation endpoint (`POST /v1/licenses/validate`) to verify keys, enforce activation limits, and handle expiry for subscription-based software.
- When tracking affiliate sales, configure the built-in affiliate program with custom commission rates and attribution windows instead of adding a third-party affiliate tool.

## Examples

### Example 1: Add subscription billing to a SaaS app

**User request:** "Set up Lemon Squeezy subscriptions for my SaaS with free trial"

**Actions:**
1. Create product with Starter and Pro variants in the dashboard, each with monthly/yearly pricing and a 14-day trial
2. Generate checkout links and integrate Lemon.js overlay in the app
3. Set up webhook endpoint to handle `subscription_created` and `subscription_payment_failed` events
4. Store `customer_id` and `subscription_id` in the database linked to the user

**Output:** A SaaS app with tiered subscription billing, free trials, and automated webhook-driven entitlement management.

### Example 2: Sell desktop software with license keys

**User request:** "Add license key validation for my Electron app sold through Lemon Squeezy"

**Actions:**
1. Configure the product with license key generation enabled and activation limits
2. Build an activation flow in the app that calls `POST /v1/licenses/validate`
3. Handle activation, deactivation, and expiry states in the app UI
4. Set up webhooks to track new purchases and subscription renewals

**Output:** A desktop app with license key activation, device limits, and automatic renewal handling.

## Guidelines

- Always verify webhook signatures with `crypto.timingSafeEqual()` to prevent forged payloads.
- Store `customer_id` and `subscription_id` in your database and link them to your user model.
- Use `checkout[custom][user_id]` to pass your internal user ID during checkout for easy reconciliation from webhooks.
- Handle `subscription_payment_failed` gracefully by notifying users rather than immediately revoking access.
- Check subscription status server-side on every protected request; do not trust client-side state.
- Use license keys for desktop and CLI software; use webhook-based entitlements for web SaaS.
