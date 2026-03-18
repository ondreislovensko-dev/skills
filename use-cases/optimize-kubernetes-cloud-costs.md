---
title: "Optimize Kubernetes Cloud Costs with AI"
slug: optimize-kubernetes-cloud-costs
description: "Audit Kubernetes clusters for resource waste, right-size workloads, and cut cloud bills by 30-50% using AI-driven analysis."
skills: [k8s-cost-optimizer, cloud-resource-analyzer]
category: devops
tags: [kubernetes, cloud-costs, resource-optimization, finops, infrastructure]
---

# Optimize Kubernetes Cloud Costs with AI

## The Problem

Ravi is a platform engineer at a 40-person fintech startup. The AWS bill climbed from $8,200 to $14,600/month over six months, and nobody can explain why. No major new services launched. No traffic spikes. Just a steady creep upward.

The root cause is invisible without investigation: developers request 2 CPU and 4Gi memory for pods that actually use 0.3 CPU and 512Mi at peak. Nobody adjusts the numbers after the initial deployment because there's no process for it and no visibility into actual usage. Namespaces accumulate idle deployments from abandoned feature branches — staging has 22 deployments, and 9 of them haven't received a single request in over a week. LoadBalancer services sit unused at $15-20/month each. The cluster is paying for 2-3x the resources it actually needs, spread across 200+ deployments in 8 namespaces.

The finance team starts asking questions. The CTO asks Ravi to "figure out what's going on with AWS." But auditing 200+ deployments by hand, comparing requested resources to actual metrics for each one, would take days. And even if he did it once, the numbers would drift again within a month.

## The Solution

Using the **k8s-cost-optimizer** and **cloud-resource-analyzer** skills, the approach is to pull live metrics from the cluster, compare actual usage against resource requests, identify zombie workloads and orphaned cloud resources, and produce right-sizing manifests with estimated savings for each change.

## Step-by-Step Walkthrough

### Step 1: Audit Resource Allocation vs. Actual Usage

```text
Connect to our production k8s cluster and analyze resource allocation efficiency.
Compare CPU and memory requests/limits against actual usage from metrics-server
for all namespaces. Show me the biggest gaps.
```

The waste report tells the story immediately. Three examples from the `api-services` namespace:

| Deployment | Requested | Actual Peak | Waste |
|---|---|---|---|
| payments-api | 2 CPU / 4Gi | 0.4 CPU / 780Mi | 80% |
| search-svc | 4 CPU / 8Gi | 1.1 CPU / 2.3Gi | 68% |
| notifications | 1 CPU / 2Gi | 0.08 CPU / 120Mi | 93% |

The notifications service is the most egregious — it's requesting 12x more CPU and 17x more memory than it ever uses. Someone set those values during initial deployment and never revisited them. This pattern repeats across the cluster: developers copy resource blocks from existing deployments or use generous defaults "just to be safe," and the numbers never get validated against reality.

The staging namespace is worse. Nine deployments have received zero requests in the last 7 days. These are zombie workloads from old feature branches that were merged or abandoned without cleaning up their Kubernetes resources. They're consuming 8 vCPUs and 16Gi memory — roughly $420/month doing nothing.

Top 5 savings opportunities:

1. Right-size search-svc replicas: **~$340/month**
2. Remove 9 zombie staging deployments: **~$280/month**
3. Right-size payments-api: **~$190/month**
4. Switch notifications to burstable tier: **~$95/month**
5. Consolidate 3 nginx ingress replicas: **~$60/month**

**Total estimated monthly savings: $965/month ($11,580/year)**

### Step 2: Generate Right-Sizing Manifests

```text
Generate patched Kubernetes manifests for the top 5 recommendations.
Use the p99 usage from the last 14 days plus a 30% headroom buffer.
Output as kustomize patches I can review and apply.
```

The patches use real usage data, not guesswork. Here's the payments-api patch — p99 CPU over 14 days was 400m, so the new request is 520m (400m + 30% buffer):

```yaml
# patches/payments-api-resources.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payments-api
  namespace: api-services
spec:
  template:
    spec:
      containers:
      - name: payments-api
        resources:
          requests:
            cpu: "520m"      # p99: 400m + 30% buffer
            memory: "1014Mi" # p99: 780Mi + 30% buffer
          limits:
            cpu: "800m"
            memory: "1536Mi"
```

The 30% buffer is important. Right-sizing to p99 exactly leaves no headroom for unexpected spikes. The buffer provides safety margin while still cutting waste by more than 70%. For the search service, the picture is different — its traffic is highly seasonal, peaking during business hours and dropping to near-zero overnight. The patch accounts for peak-hour p99, not 24-hour p99, to avoid under-provisioning during the busy period.

The notifications service gets a different treatment entirely. At 0.08 CPU peak usage, it doesn't need dedicated compute — it's a perfect candidate for a burstable instance type or node pool, where it can burst to higher CPU when processing a batch of notifications but pay only for its baseline consumption.

### Step 3: Find Orphaned Cloud Resources Outside the Cluster

```text
Now check our AWS account for cloud resources attached to this cluster that
might be orphaned — unused EBS volumes, old snapshots, unattached elastic IPs,
and idle load balancers with zero healthy targets.
```

Kubernetes isn't the only source of waste. The AWS account has accumulated debris from months of operations — resources created during incidents, migrations, and experiments that were never cleaned up:

| Resource Type | Details | Monthly Cost |
|---|---|---|
| Unattached EBS volumes | 3 volumes (100Gi + 250Gi + 50Gi), oldest from June 2025 | $32.00 |
| Unassociated Elastic IPs | 3 IPs sitting idle | $10.80 |
| ELBs with 0 healthy targets | 2 load balancers from decommissioned services | $36.00 |
| Stale snapshots | 47 snapshots older than 90 days from a DB migration | $28.00 |

**Total orphaned resource cost: $106.80/month.** The 250Gi EBS volume tagged `old-postgres-data` has been sitting unattached since a database migration three months ago — $20/month for data that's already been migrated and verified. The 47 snapshots are from the same migration; the team kept them "just in case" and forgot about them.

### Step 4: Create a Cleanup Plan with Safety Checks

```text
Create a cleanup script for the orphaned resources. Include dry-run mode,
tag verification, and a 7-day grace period where resources get tagged
for-deletion before actual removal.
```

Deleting cloud resources is irreversible, so the cleanup follows a two-phase approach with built-in safety:

**Phase 1 — Tag for deletion (safe, reversible):** Resources get a `scheduled-deletion` tag with a date 7 days in the future. Nothing is actually deleted. An alert goes to Slack listing every tagged resource so the team can review.

```bash
# Tag resources for deletion with 7-day grace period
aws ec2 create-tags --resources vol-0a3f8c912b \
  --tags Key=scheduled-deletion,Value=2026-02-25

# Tag stale snapshots in bulk
aws ec2 describe-snapshots --filters "Name=start-time,Values=*2025-08*" \
  --query 'Snapshots[].SnapshotId' --output text | \
  xargs -I {} aws ec2 create-tags --resources {} \
  --tags Key=scheduled-deletion,Value=2026-02-25
```

**Phase 2 — Delete after grace period (runs daily via cron):** A cleanup job checks for resources whose `scheduled-deletion` date has passed and removes them. If someone realizes a volume is still needed during the 7-day window, they simply remove the tag.

Dry-run mode prints what would happen without making changes. Every action is logged to CloudWatch for audit trails. The script refuses to delete any resource that's currently attached or in use, regardless of its tags.

## Real-World Example

Ravi applies the kustomize patches to staging first and monitors for a week. No alerts, no performance issues, no customer impact. The pods run happily at their new, right-sized resource levels. He watches the metrics closely during peak hours — the 30% buffer holds comfortably.

He rolls the changes to production and deletes the 9 zombie staging deployments. The orphaned EBS volumes and stale snapshots get tagged for deletion with the 7-day grace period. Nobody claims any of them during the window.

Within one sprint, the monthly bill drops from $14,600 to $11,200 — a 23% reduction with zero performance impact. The search service, which was provisioned for Black Friday traffic year-round, accounts for the single largest savings at $340/month. Ravi sets up a monthly re-audit as a recurring calendar event — 30 minutes once a month to catch drift before it accumulates for another six months. He also adds a Slack bot that alerts when any new deployment is created with requests exceeding 2x the namespace average, catching overprovisioning at the source instead of cleaning it up after the fact.
