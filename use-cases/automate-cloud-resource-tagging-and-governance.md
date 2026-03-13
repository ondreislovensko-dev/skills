---
title: "Automate Cloud Resource Tagging and Governance with AI"
slug: automate-cloud-resource-tagging-and-governance
description: "Enforce consistent resource tagging across cloud infrastructure to enable cost allocation, compliance, and cleanup of orphaned resources."
skills: [coding-agent, report-generator, hetzner-cloud]
category: devops
tags: [cloud-governance, tagging, cost-allocation, infrastructure, compliance]
---

# Automate Cloud Resource Tagging and Governance with AI

## The Problem

A 40-person engineering organization runs 200+ cloud resources across multiple environments. Only 60% of resources have proper tags, making it impossible to accurately allocate costs to teams, identify which environment a resource belongs to, or determine if something is still in use. Last month, the finance team asked engineering to break down cloud costs by product — nobody could answer because half the resources have no team or project tags. Meanwhile, 15% of the bill goes to orphaned resources from projects that ended months ago, but nobody can tell which ones are safe to delete.

The problem compounds over time. Every engineer who spins up a resource and forgets to tag it adds noise. Every project that wraps up without cleaning its resources adds cost. Six months from now, 200+ resources becomes 300+, and the untagged percentage creeps higher because new resources get created faster than old ones get tagged. Manual tagging sprints help temporarily — someone spent a full week in the console last quarter clicking through resource after resource — but compliance drifts back below 60% within two months as new untagged resources accumulate.

The fundamental issue is that tagging is a creation-time problem being treated as a cleanup problem. No amount of quarterly audits will fix tagging compliance if the creation process does not require tags in the first place.

## The Solution

Use the **coding-agent** to build tagging automation scripts that audit, fix, and enforce resource tags, **report-generator** to create governance dashboards, and **hetzner-cloud** for cloud infrastructure management patterns that apply across providers.

## Step-by-Step Walkthrough

### Step 1: Audit Current Tagging State

```text
Audit all our cloud resources for tagging compliance. Required tags are: team, environment, project, and cost-center. Show me which resources are missing tags, which have inconsistent values, and what percentage are fully compliant.
```

The audit scans 214 resources and the results explain why Finance cannot get answers:

**Overall compliance: 58%** — only 124 out of 214 resources have all four required tags.

Missing tags by category:

| Required Tag | Resources Missing It | Why It Matters |
|---|---|---|
| `team` | 43 | Cannot allocate costs to teams |
| `cost-center` | 37 | Cannot map to Finance's budget codes |
| `project` | 28 | Cannot track project-level spend |
| `environment` | 12 | Cannot separate prod from staging costs |

But missing tags are only half the problem. The tags that *do* exist are inconsistent. The `environment` tag has four different spellings of production: `"prod"`, `"production"`, `"PROD"`, `"prd"`. The `team` tag has 8 variations for just 3 teams — `"backend"`, `"Backend"`, `"back-end"`, `"BE"`, and more. Any dashboard or query grouping by these tags produces fragmented results — you see "backend" as one line and "Backend" as another, splitting one team's costs into two rows.

The worst offenders by resource type: 15 untagged S3 buckets (many with generic names like `data-backup-2` that could belong to any team), 12 untagged Lambda functions (often created by developers experimenting and forgotten), and 9 untagged RDS snapshots (automated backups from instances that may or may not still exist).

The inconsistency problem is arguably worse than the missing-tags problem. Missing tags are obviously broken — you know you need to fix them. Inconsistent tags *look* fine until you try to aggregate data. A cost report that groups by the `team` tag will show "backend" and "Backend" as two separate teams, each with incomplete numbers. The person reading the report has to know that these are the same team and mentally merge the numbers — if they even notice the split.

### Step 2: Auto-Fix Tagging Issues

```text
Fix the inconsistent tag values — normalize environment to prod/staging/dev and team names to their canonical forms. For resources missing tags, infer what you can from resource names, VPC placement, and creation metadata. Show me what you'd change before applying.
```

Before changing anything, a dry-run shows exactly what will happen. No surprises, no accidental overwrites. Tags get fixed in two categories:

**Auto-inferred tags (high confidence):**
- 31 resources get `environment` inferred from their VPC or subnet placement — resources in the `vpc-prod-us-east-1` VPC are clearly production, and `subnet-staging-private` leaves no ambiguity
- 18 resources get `team` inferred from the IAM role that created them — if the `data-engineering-deploy-role` created a Lambda function, the team is `data`
- 12 resources get `project` inferred from their name prefix — `etl-pipeline-worker-03` clearly belongs to the `etl-pipeline` project

**Normalization fixes:**
- 23 resources with inconsistent `environment` values get standardized (`"production"` becomes `"prod"`, `"PROD"` becomes `"prod"`, `"prd"` becomes `"prod"`)
- 14 resources with inconsistent `team` values get canonical names (`"Backend"`, `"back-end"`, and `"BE"` all become `"backend"`)

**Cannot infer (27 resources):** these need manual review. A CSV file — `untagged-resources-review.csv` — lists each resource with its creation date, creator IAM principal, VPC, and any partial tags to help identify ownership. These are the resources most likely to be orphans — if nobody recognizes them, they are probably safe to decommission.

After applying the dry-run changes, compliance jumps from 58% to 87% without any manual console clicking. The remaining 13% are the 27 resources that need manual review — resources with no name patterns, no VPC context, and no identifiable creator. These are the ones most likely to be orphans, and the review CSV makes it easy to triage them in a 30-minute meeting with the team leads ("Does anyone recognize a Lambda function called `test-handler-3` created on August 14th?").

### Step 3: Set Up Enforcement Policies

```text
Create policies that prevent untagged resources from being created and detect compliance drift over time.
```

Four governance mechanisms prevent the tagging problem from recurring:

**Pre-deploy validation** — a Terraform plan validator that rejects any resource missing required tags before it can be created:

```hcl
# modules/tag-enforcement/main.tf
variable "required_tags" {
  default = ["team", "environment", "project", "cost-center"]
}

resource "null_resource" "tag_check" {
  for_each = var.resources
  lifecycle {
    precondition {
      condition = alltrue([
        for tag in var.required_tags : contains(keys(each.value.tags), tag)
      ])
      error_message = "Resource ${each.key} is missing required tags: ${join(", ", var.required_tags)}"
    }
  }
}
```

This is the most important piece. It shifts tagging from a cleanup task to a creation requirement. Developers learn quickly when their `terraform apply` fails with a clear error message telling them exactly which tags are missing.

**Nightly compliance audit** — a scheduled script scans all resources, compares against the required tag policy, and posts a report to Slack. If compliance drops below 90%, the message tags the platform team lead. This catches resources created outside of Terraform — through the console, CLI scripts, or third-party tools.

**Orphan detection** — flags resources with no traffic, no connections, and no API calls for 30+ days. These go into a "review" queue rather than being deleted automatically — the last thing anyone wants is to auto-delete a disaster recovery snapshot that only gets used during actual disasters.

**Weekly cost report** — breaks down spend by team and project using tag data, delivered to team leads every Monday. This creates accountability. When a team can see their own spend alongside other teams, they start caring about optimization without being told to. The report includes week-over-week changes, so a sudden $500 increase gets noticed the following Monday instead of hiding in the monthly bill.

**Tag value validation** — in addition to requiring tags to exist, the nightly audit validates that tag values are from the allowed set. A resource tagged `environment: prodution` (note the typo) gets flagged just like a resource with no environment tag at all. This prevents the normalization problem from recurring with new creative misspellings.

### Step 4: Identify Orphaned Resources for Cleanup

```text
Find all resources that appear to be orphaned — no traffic, no connections, created more than 90 days ago, and associated with completed or unknown projects.
```

The orphan report separates high-confidence deletions from resources that need human review:

**Safe to delete (high confidence):**

| Resource | Age | Cost/Month | Why It's Orphaned |
|---|---|---|---|
| 4 EBS volumes | 90+ days | $210 | Unattached since parent instances were terminated |
| 3 Elastic IPs | 120+ days | $10.95 | Not associated with any running resource |
| 7 old snapshots | 150+ days | $45 | Created from instances that no longer exist |

**Review recommended:**

| Resource | Age | Cost/Month | Notes |
|---|---|---|---|
| 2 RDS instances | 60+ days | $340 | No connections in 60 days, but tagged as `disaster-recovery` — verify before deleting |
| 5 Lambda functions | 90+ days | minimal | 0 invocations, but one is named `quarterly-tax-export` — it may run once per quarter |

**Potential monthly savings: $605.95** from the high-confidence deletions alone, plus $340 if the RDS instances are confirmed as orphans after verifying the disaster recovery plan does not depend on them.

The Lambda function case is equally nuanced. A function named `quarterly-tax-export` with 0 invocations in 90 days looks unused — but if the last invocation was 91 days ago and the function runs on the first of every quarter, deleting it means the next tax export silently fails. The orphan report includes last-invocation timestamps and function triggers to help make the call.

The RDS case illustrates why automatic deletion is dangerous. A database with no connections for 60 days looks dead — but if it is the disaster recovery standby, deleting it means the next actual disaster has no failover. The orphan report flags it but requires a human to make the call. Good governance automates detection, not destruction.

## Real-World Example

Dani is the platform engineer at a 40-person e-commerce company. Finance is asking for cost allocation by team, but 42% of cloud resources have no team tag. She has been asked this question before and spent a full week manually tagging resources in the console — clicking through each resource, looking up who created it, assigning the right team. By the time she finished, compliance hit 85%. Two months later, it was back below 60% as new resources got created without tags.

She runs the full tagging workflow in a single afternoon. The audit reveals 58% compliance and 8 different spellings of team names across resources. Auto-inference tags 61 resources using VPC placement and IAM creator data, and normalization fixes another 37. Compliance jumps from 58% to 87% without any manual console clicking — the same result as her week-long manual effort, done in hours.

The critical difference this time is enforcement. The Terraform validation policy prevents the drift problem — no resource can be created without all four required tags. The nightly audit catches any resources that slip through (manually created via the console, for example) and flags them within 24 hours instead of letting them accumulate for months.

Six weeks later, compliance sits at 96%. The orphan detection has identified $605 per month in wasted resources, which get cleaned up in a single PR after verifying the disaster recovery instances are accounted for in a separate DR plan. The two RDS instances turn out to be legitimate disaster recovery standbys — but they were never tagged as such, which is why they looked orphaned. They get proper tags and a note in the runbook.

And for the first time, Dani delivers the cost allocation report Finance wanted — broken down by team and project, with trend lines showing which teams are optimizing and which are growing unchecked. The data team's spend is up 31%, and now there is a tag trail showing exactly which project drove the increase. Finance uses the breakdown for the quarterly board deck, and the CTO uses the team-level trends for headcount planning conversations. The tags that seemed like bureaucratic overhead to the engineering team turn out to be the foundation for every financial question the business needs to answer about infrastructure.
