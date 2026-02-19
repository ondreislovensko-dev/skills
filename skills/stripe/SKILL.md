---
name: stripe
description: >-
  Assists with building payment systems using the Stripe platform. Use when integrating
  Checkout, Payment Intents, subscriptions, marketplace payouts via Connect, or invoice
  management with proper webhook handling and PCI compliance. Trigger words: stripe,
  payments, checkout, subscriptions, billing, connect, invoices.
license: Apache-2.0
compatibility: "Requires Node.js 16+"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: business
  tags: ["stripe", "payments", "subscriptions", "billing", "checkout"]
---

# Stripe

## Overview

Stripe is a payment processing platform for building complete payment systems, supporting one-time payments via Checkout, recurring billing with Subscriptions, marketplace payouts through Connect, and invoice management. It provides client-side SDKs (Stripe.js, Elements), server-side libraries, webhook handling, and built-in fraud prevention through Radar.

## Instructions

- When accepting payments, prefer Stripe Checkout for new integrations since it handles edge cases (3D Secure, SCA, error states) automatically; use Payment Intents with Elements only when a fully custom payment UI is required.
- When setting up subscriptions, define products and prices in Stripe (or via API), create subscriptions with `stripe.subscriptions.create()`, and handle lifecycle events (`invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`) via webhooks.
- When handling webhooks, always verify signatures with `stripe.webhooks.constructEvent()` and handle idempotency by checking if the event was already processed before taking action.
- When building marketplaces, use Stripe Connect with the appropriate account type (Standard for Stripe-hosted onboarding, Express for branded onboarding, Custom for full control) and choose between direct charges and destination charges.
- When managing customer billing, create a Customer Portal session with `stripe.billingPortal.sessions.create()` to let customers update payment methods, switch plans, and view invoices.
- When collecting payments on the client, use `PaymentElement` for a universal payment form that supports cards, wallets, and bank transfers, or `CardElement` for simple card-only integrations.

## Examples

### Example 1: Add subscription billing to a SaaS application

**User request:** "Set up Stripe subscriptions with monthly and yearly plans for my SaaS"

**Actions:**
1. Create products and prices in Stripe for each plan tier (monthly and yearly)
2. Integrate Stripe Checkout with `mode: "subscription"` and trial period
3. Set up webhook endpoint handling `invoice.paid`, `invoice.payment_failed`, and `customer.subscription.deleted`
4. Add Customer Portal integration for self-service billing management

**Output:** A SaaS app with subscription billing, free trials, automatic dunning, and customer self-service portal.

### Example 2: Build a marketplace with seller payouts

**User request:** "Create a marketplace where sellers receive payouts through Stripe Connect"

**Actions:**
1. Set up Stripe Connect with Express accounts for seller onboarding
2. Create checkout flow with destination charges that split payment between platform and seller
3. Handle `account.updated` webhooks to track seller verification status
4. Build a seller dashboard showing balance, payouts, and transfer history

**Output:** A marketplace with seller onboarding, automatic payment splitting, and payout management.

## Guidelines

- Always verify webhook signatures with `stripe.webhooks.constructEvent()` and never trust unverified payloads.
- Store `customer.id` in your database and link your users to Stripe customers at registration time.
- Handle webhook idempotency: check if the event has already been processed before taking action.
- Use `metadata` on every Stripe object to store internal IDs (userId, orderId) for reconciliation.
- Use `price` objects defined in Stripe rather than raw amounts to keep pricing centralized.
- Never log full card numbers or payment method details to maintain PCI compliance.
- Use Checkout for new integrations unless a custom payment UI is specifically required.
