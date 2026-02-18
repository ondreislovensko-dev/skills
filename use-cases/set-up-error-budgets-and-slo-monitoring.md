---
title: "Set Up Error Budgets and SLO Monitoring for Your Services"
slug: set-up-error-budgets-and-slo-monitoring
description: "Define SLIs, set SLO targets, calculate error budgets, and build dashboards that tell your team when to ship features vs. fix reliability."
skills: [data-analysis, report-generator, cicd-pipeline]
category: devops
tags: [sre, slo, error-budget, reliability, monitoring, observability]
---

# Set Up Error Budgets and SLO Monitoring for Your Services

## The Problem

The engineering team ships features every sprint, but nobody knows if the platform is "reliable enough." When incidents happen, the same argument erupts: "Should we freeze releases?" versus "We need to ship this feature by Thursday." The SRE team says uptime is 99.9%. Product says customers are complaining about intermittent errors. Neither side has data to settle it.

There are no formal SLOs. No error budgets. Reliability decisions are made by gut feeling and whoever argues loudest in the sprint planning meeting. The team needs a system that answers one question with data: should we ship features this week, or fix reliability?

## The Solution

Using the **data-analysis**, **report-generator**, and **cicd-pipeline** skills, this walkthrough defines SLIs from existing Prometheus and Datadog metrics, calculates SLO targets based on 90 days of historical data, builds Grafana dashboards with error budget burn-down charts, and gates deployments automatically when budgets run low.

## Step-by-Step Walkthrough

### Step 1: Define SLIs That Reflect User Experience

Most teams monitor server metrics -- CPU, memory, disk. But customers do not care about CPU usage. They care about whether the page loads, whether checkout works, and whether search results appear quickly. SLIs need to measure what users experience:

```text
We run 6 production services behind an API gateway. We have Prometheus metrics
for request latency (histogram), HTTP status codes (counter), and uptime
(gauge). We also have business metrics in Datadog: checkout completion rate,
search result relevance score, and notification delivery time.

For each service, recommend the right SLIs. Map each SLI to the specific
Prometheus or Datadog metric, and write the PromQL/Datadog query to calculate
it. Focus on what customers actually experience, not internal metrics.
```

Fourteen SLIs come out across 6 services. The most important ones:

**API Gateway availability** -- the percentage of requests that do not return a 5xx error:

```promql
sum(rate(http_requests_total{status!~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
```

This is what users feel directly. Every 5xx is a user seeing an error page.

**API Gateway latency** -- p99 response time under 500ms. Users do not notice 200ms versus 300ms, but they absolutely notice when a page takes 2 seconds.

**Checkout success rate** -- from Datadog business metrics, the percentage of checkout attempts that complete successfully. This ties directly to revenue.

Each SLI has a precise query and a justification for why it matters to users, not just to the operations team.

### Step 2: Set SLO Targets from Historical Data

SLO targets pulled from thin air are either too aggressive (constant alerts, team ignores them) or too lenient (meaningless). Historical data sets the right level:

```text
Pull the last 90 days of data for each SLI and calculate the baseline
reliability. For each one, recommend an SLO target that's achievable but
meaningful. Show me: current performance (p50, p95, p99 over 90 days),
recommended SLO, the implied error budget in minutes per month, and what
would have triggered an error budget alert in the last 90 days.
```

The analysis produces concrete targets:

| SLI | Current (90-day) | Recommended SLO | Error Budget |
|-----|-------------------|----------------|--------------|
| API availability | 99.97% | 99.95% | 21.6 minutes downtime/month |
| API latency p99 | 420ms | 500ms | ~22 minutes of slow responses/month |
| Checkout success | 99.72% | 99.5% | ~50 failed checkouts/month at current volume |

The API availability target of 99.95% gives the team 21.6 minutes of downtime per month as their error budget. The current 99.97% performance means there is headroom -- but not much. Two incidents last quarter would have burned 73% of the monthly budget. A third would have exhausted it.

This is exactly the kind of data that settles the "ship vs. fix" debate. If the budget is 80% full, the answer is obvious: fix reliability this sprint.

### Step 3: Build Error Budget Dashboards

The SLO targets need to be visible to every team, not buried in a spreadsheet:

```text
Create Grafana dashboard JSON for each service showing:
- Current SLO compliance (rolling 30-day window)
- Error budget remaining (percentage and absolute)
- Error budget burn rate (are we burning faster than expected?)
- Time until budget exhaustion at current burn rate
- Incident markers overlaid on the budget burn-down chart

Use traffic-light colors: green (>50% budget), yellow (20-50%), red (<20%).
```

The Grafana dashboards use 6 panels per service. The most critical panel is the burn rate chart, which uses a multi-window approach:

- **1-hour burn rate exceeds 14.4x:** the budget would exhaust in 5 hours. This triggers an immediate page.
- **6-hour burn rate exceeds 6x:** the budget would exhaust in 2 days. This triggers a warning alert.

The multi-window approach catches both fast incidents (service goes down hard) and slow burns (elevated error rate from a bad deploy that is not quite bad enough to trigger traditional alerting).

Traffic-light colors make the dashboard readable at a glance: green means more than 50% of budget remains, yellow means 20-50%, and red means less than 20% -- time to stop shipping features and fix reliability.

### Step 4: Gate Deployments on Error Budget

The dashboard tells humans what to do. The deployment gate enforces it automatically:

```text
Add a deployment gate to our GitHub Actions pipeline. Before deploying to
production, check the current error budget status via Prometheus API.
If error budget is below 20%, block the deployment and post a Slack message
explaining why. Allow override with a "deploy-override" label on the PR,
but log every override. If budget is between 20-50%, add a warning comment
to the PR but allow deployment.
```

The GitHub Actions job queries Prometheus before every production deploy:

- **Budget > 50%:** Deploy proceeds normally. Ship with confidence.
- **Budget 20-50%:** PR gets a warning comment: "Error budget at 35%. Deploy with caution." Deployment proceeds but the team is aware.
- **Budget < 20%:** Deployment is blocked. Slack message explains: "Production deploy blocked -- API availability error budget at 12%. Focus on reliability before shipping new features." A `deploy-override` label on the PR bypasses the gate, but every override is logged to a Slack channel and requires SRE approval.

### Step 5: Automate the Weekly Reliability Report

The final piece turns all this data into a sprint planning input:

```text
Generate a weekly report template that automatically pulls data and shows:
- SLO compliance across all services
- Error budget consumed this week vs. previous weeks (trend)
- Top 3 error budget consumers (specific endpoints or error types)
- Recommendation: "ship features" or "focus on reliability" based on budget
- Action items from any SLO breaches

Format as markdown suitable for posting in Slack.
```

The report generator queries Prometheus and Datadog every Monday at 9 AM and posts to Slack. The recommendation engine is simple: budget above 50% means "ship features," 20-50% means "balance both," and below 20% means "reliability sprint." The report includes sparkline-style trend indicators so the team can see whether reliability is improving or degrading week over week.

## Real-World Example

In the first month, the deployment gate blocks 2 production deploys when the error budget drops below 20%. Both times, the team investigates and finds a regression from a recent release that had been slowly burning the budget -- not enough to trigger traditional alerting, but enough to exhaust the monthly budget in a week. The regressions get fixed before they reach more customers.

The weekly reliability report becomes a fixture in sprint planning. Instead of the "ship vs. fix" argument, the team looks at the error budget number and makes a data-driven decision. When the budget is healthy, product gets their features. When it is low, engineering focuses on reliability. The heated debate disappears because both sides are looking at the same data.

Three months in, the SRE lead tracks the results: the mean time between customer-facing incidents doubles. The number of "should we freeze releases" emergency meetings drops to zero. And product velocity actually increases -- the team ships more features per quarter because they spend less time fighting fires and debating reliability in meetings.
