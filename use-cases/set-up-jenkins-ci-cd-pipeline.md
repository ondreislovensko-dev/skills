---
title: "Set Up a Jenkins CI/CD Pipeline for Multi-Service Deployments"
slug: set-up-jenkins-ci-cd-pipeline
description: "Build a production Jenkins pipeline with shared libraries, Docker agents, parallel testing, Kubernetes deployment, and automated rollbacks across multiple services."
skills: [jenkins-pipelines, docker-helper, kubernetes-helm]
category: devops
tags: [jenkins, ci-cd, pipeline, deployment, automation, devops]
---

# Set Up a Jenkins CI/CD Pipeline for Multi-Service Deployments

## The Problem

A 30-person engineering team runs Jenkins with 15 jobs configured through the UI. Every job is a snowflake — different build scripts, inconsistent test stages, no shared logic. Pipeline changes require clicking through the Jenkins web UI, and nobody knows which job does what without reading the messy shell scripts buried in each build step.

Builds run on a single overloaded Jenkins controller with no agents, which means a 45-minute queue every morning when everyone pushes at once. There are no automated deployments — someone runs a deploy script manually after a passing build. Three times last quarter, a broken build was deployed to production because someone skipped the test step.

The worst part: if the Jenkins server dies, all 15 jobs disappear. Nothing is in code.

## The Solution

Use **jenkins-pipelines** to migrate all jobs to Jenkinsfiles with shared libraries, **docker-helper** to containerize build environments for reproducibility, and **kubernetes-helm** to automate deployments from the pipeline.

## Step-by-Step Walkthrough

### Step 1: Migrate from UI Jobs to Jenkinsfiles

```text
We have 15 Jenkins jobs configured in the UI for 5 services (API, frontend,
auth, worker, shared-lib). Each service has build, test, and deploy steps
but they're all slightly different. Audit all 15 jobs and create a
standardized Jenkinsfile for each service. Use Declarative Pipeline syntax.

Common stages: checkout -> install -> lint -> test (parallel: unit + integration)
-> build Docker image -> push to ECR -> deploy to staging -> deploy to production
(with manual approval). Post: Slack notification, test report archiving,
workspace cleanup.
```

The audit reveals a familiar pattern: 15 jobs that are 80% identical and 20% snowflake. All five services follow the same flow — checkout, install, lint, test, build, deploy — but each one implements it differently because whoever set it up that day had slightly different ideas.

The resulting Jenkinsfiles standardize the structure. Every service gets identical stage names, parallel test execution, Docker image building with commit SHA tags, and environment-specific deploy stages with proper gating. The per-service differences (Node vs Python build commands, different test runners) are isolated to a few lines each.

### Step 2: Build a Shared Library for Common Pipeline Logic

```text
Extract the common pipeline logic into a Jenkins Shared Library:
- buildDockerImage(name, dockerfile, registry): builds, tags with git SHA, pushes
- runTests(type: 'node'|'python'|'go'): installs deps and runs tests per language
- deployToK8s(service, environment, imageTag): helm upgrade with proper values
- notifySlack(channel, status): success/failure notification with build details
- securityScan(type: 'npm'|'trivy'): runs npm audit or Trivy image scan

The library should be versioned in git. Jenkinsfiles should be 20-30 lines
max, calling library functions for all the heavy lifting.
```

This is where the real cleanup happens. The shared library repo gets a `vars/` directory with global functions and a `src/` directory for helper classes. Each function handles error cases and provides sensible defaults — `runTests('node')` knows to run `npm ci && npm test`, while `runTests('python')` uses `pip install -r requirements.txt && pytest`.

The Jenkinsfiles shrink from 200+ lines of duplicated shell scripts to roughly 25 lines each:

```groovy
// Jenkinsfile — API service
@Library('pipeline-lib') _

pipeline {
  agent { kubernetes { yamlFile 'jenkins/pod-template.yaml' } }
  stages {
    stage('Test')   { steps { runTests('node') } }
    stage('Build')  { steps { buildDockerImage('api', './Dockerfile', 'ECR_REGISTRY') } }
    stage('Deploy') { steps { deployToK8s('api', env.BRANCH_NAME == 'main' ? 'production' : 'staging', env.GIT_COMMIT) } }
  }
  post { always { notifySlack('#deploys', currentBuild.result) } }
}
```

Pipeline changes now go through code review like everything else.

### Step 3: Set Up Dynamic Kubernetes Agents

```text
Our Jenkins controller is overloaded running builds directly. Set up
Kubernetes-based agents that spin up per-build and die after:
- Node.js pod template: node:20 + docker-in-docker for building images
- Python pod template: python:3.11 + pip cache volume
- Go pod template: golang:1.22 + module cache volume
- Shared npm/pip cache across builds using PVC

Configure the Jenkins Kubernetes plugin, create pod templates, and update
all Jenkinsfiles to use the appropriate agent for each service.
```

The Jenkins Kubernetes plugin gets configured via JCasC (Configuration as Code). Three pod templates are created, each with the right tool containers and shared cache PVCs. Resource requests and limits prevent noisy neighbor problems — one runaway build can't starve the others.

The difference is dramatic. Before: 15 builds queued on a single machine, 45-minute waits. After: 15 builds run in parallel on ephemeral Kubernetes pods, each spinning up in seconds and dying when done. Build queue time drops from 45 minutes to under 2 minutes.

### Step 4: Add Quality Gates and Automated Rollbacks

```text
Add quality gates to the pipeline:
1. Code coverage must be >80% or the build fails
2. Trivy image scan: no critical/high CVEs
3. Lint must pass with zero warnings
4. Integration tests run against a temporary namespace with test database
5. Performance test: API response time must be <200ms p95

For deployments: if the health check fails after deploy to staging or
production, automatically rollback to the previous Helm release.
Add a /rollback slash command in Jenkins for manual rollbacks.
```

Each quality gate gets its own stage with hard thresholds. Integration tests spin up a dynamic namespace with a fresh database, run the suite, and tear everything down in `post { always }` — no test namespace pollution.

The rollback mechanism is the real safety net. If a health check fails after deployment, the pipeline automatically runs `helm rollback` to the previous release. A separate parameterized "Rollback" job accepts a service name and revision number for manual rollbacks. The k6 performance test runs a quick load scenario with pass/fail criteria — if p95 exceeds 200ms, the pipeline stops before reaching production.

### Step 5: Jenkins Configuration as Code and Disaster Recovery

```text
Our Jenkins config exists only in the UI — if the server dies, we lose
everything. Set up:
1. Jenkins Configuration as Code (JCasC) covering: security, agents,
   credentials (from Kubernetes secrets), shared library config, and all
   global settings
2. Job DSL or seed jobs that auto-create multibranch pipelines for every
   repo in our GitHub org
3. Automated backup of Jenkins home to S3 (daily)
4. Document the full disaster recovery procedure: how to restore Jenkins
   from scratch in under 30 minutes
```

The JCasC YAML captures every Jenkins setting — security realm, authorization, cloud agents, credential bindings (pulling from Kubernetes secrets), and shared library configuration. A seed job using Job DSL scans the GitHub org and creates multibranch pipeline jobs automatically for any repo containing a `Jenkinsfile`.

A backup CronJob snapshots the Jenkins PVC to S3 daily. The recovery runbook has exact commands: deploy Jenkins from Helm, restore the PVC snapshot, verify all jobs are back. Full disaster recovery from scratch takes under 20 minutes.

## Real-World Example

Maya leads engineering at a 30-person company. She inherits 15 snowflake Jenkins jobs configured through the UI, a single overloaded controller with 45-minute build queues, manual deploys, and broken builds reaching production 3 times per quarter.

She migrates all jobs to Jenkinsfiles backed by a shared library — pipeline changes now go through code review like any other code change. Kubernetes agents eliminate the build queue entirely: 15 parallel builds run in under 2 minutes. Quality gates block a release when Trivy flags a critical CVE that would have reached production. The automatic rollback catches a bad deploy in staging and restores the previous version in 30 seconds, before any customer notices.

After 3 months: zero bad deploys to production, pipeline changes are peer-reviewed, and Jenkins can be fully restored from scratch in 20 minutes. The morning build queue is a memory.
