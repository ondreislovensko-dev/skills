---
title: "Set Up Automated Container Security Scanning with AI"
slug: set-up-container-security-scanning
description: "Automate vulnerability scanning of Docker container images and generate remediation plans."
skills: [docker-helper, security-audit, coding-agent]
category: devops
tags: [containers, docker, security, vulnerability-scanning, devops]
---

# Set Up Automated Container Security Scanning with AI

## The Problem

Soren's team builds and deploys 15 Docker images across microservices at a healthcare startup that must pass security audits quarterly. Each image pulls in base layers, system packages, and application dependencies -- any of which could have known vulnerabilities. Everyone knows they should be scanning images, but Trivy output is a wall of CVE numbers, severity levels, and package names. The last time someone ran it against the API server, 136 vulnerabilities came back. Nobody had time to triage which ones were actually exploitable, which were false positives for their stack, and which upgrades would break things.

So the scan results sit in a Slack thread, unread, while the team ships features. Then the quarterly security audit arrives and 12 critical CVEs get flagged across container images. The compliance team is concerned. The team has 30 days to remediate, and suddenly container security is everyone's emergency.

## The Solution

Using the **docker-helper**, **security-audit**, and **coding-agent** skills, this walkthrough scans all container images, separates real risks from noise, generates actionable remediation plans with exact Dockerfile changes, and produces fixed images that pass the audit.

## Step-by-Step Walkthrough

### Step 1: Scan and Summarize All Images

Instead of dumping raw Trivy output, the scan groups findings by what actually matters -- severity and fixability:

```text
Scan our Docker images for vulnerabilities: api-server:latest, worker:latest, and web-frontend:latest. Use Trivy and give me a summary grouped by severity and fixability.
```

| Image | Base | Critical | High | Medium | Low | Size | Layers | Base Age |
|-------|------|----------|------|--------|-----|------|--------|----------|
| `api-server:latest` | `node:18-bullseye` | 3 (all fixable) | 12 (9 fixable) | 34 | 87 | 1.2 GB | 23 | 4 months |
| `worker:latest` | `python:3.11-slim` | 0 | 4 (3 fixable) | 18 | 42 | 340 MB | 14 | 2 months |
| `web-frontend:latest` | `nginx:1.24-alpine` | 1 (fixable) | 2 (2 fixable) | 8 | 15 | 45 MB | 8 | 6 months |

The headline number: **4 fixable critical and 14 fixable high vulnerabilities** across three images. The api-server is the worst offender -- an old Debian bullseye base with a 4-month-old Node image accounts for most of the findings. The web-frontend, despite being the smallest image, has a critical finding because the nginx base is 6 months old.

A pattern is already visible: most vulnerabilities come from base images and system packages, not from application code. This matters for prioritization -- base image updates are usually low-risk and high-impact.

### Step 2: Triage by Exploitability

Raw CVE counts are misleading. A critical vulnerability in a library your code never calls is less urgent than a moderate one in your hot path:

```text
For each critical and high-severity fixable vulnerability, tell me exactly what to change in the Dockerfile or package files to fix it. Prioritize by exploitability.
```

The triage reveals that not all "critical" findings are equal:

**CVE-2024-38816** (Critical) -- Spring Web path traversal in `api-server`

This is a false positive. The api-server is a Node.js service -- Spring Web is an unused transitive dependency pulled in by a Java-based build tool that exists in the full `bullseye` base image but is never invoked at runtime. Switching to a multi-stage build that only copies the Node.js runtime into the final image eliminates it entirely. Risk: none. This CVE should never have been attributed to this service.

**CVE-2025-1023** (Critical) -- OpenSSL buffer overflow in `api-server`

Real vulnerability in the base image's OpenSSL package. The api-server makes TLS connections to external APIs, so OpenSSL is in the active code path. Fix: update the base image from `node:18-bullseye` to `node:18-bookworm`. This is a single-line Dockerfile change:

```dockerfile
# Before
FROM node:18-bullseye

# After — Debian Bookworm is the current stable release
FROM node:18-bookworm
```

Risk: low. Bookworm is Debian's current stable, and the Node.js runtime is identical across both base images.

**CVE-2024-45490** (Critical) -- libexpat heap overflow in `web-frontend`

Real vulnerability in the nginx base image's XML parsing library. Even though the web-frontend is a simple static file server, libexpat is part of the Alpine base and could be exploited if the server processes any XML-like content. Fix: update from `nginx:1.24-alpine` to `nginx:1.27-alpine`. Risk: low -- nginx 1.27 is backward compatible with 1.24 config files; no configuration changes needed.

This is the value of triage: 3 "critical" vulnerabilities, but one is a false positive, and the other two are single-line base image updates. Without triage, Soren's team would be staring at 136 CVEs trying to figure out where to start.

### Step 3: Generate Fixed Dockerfiles

With the remediation plan clear, the actual fixes get applied:

```text
Generate updated Dockerfiles for all three images with the security fixes applied. Add a comment explaining each change.
```

The api-server gets the biggest overhaul. The original Dockerfile uses a single-stage build on `node:18-bullseye` -- a 1.2 GB image that includes compilers, build tools, and system libraries that have nothing to do with running a Node.js API. The updated Dockerfile uses a multi-stage build:

```dockerfile
# Build stage — full image with compilers and dev tools
FROM node:18-bookworm AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Runtime stage — only what's needed to run
FROM node:18-bookworm-slim
WORKDIR /app
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./
USER node
HEALTHCHECK --interval=30s CMD curl -f http://localhost:3000/health || exit 1
CMD ["node", "dist/server.js"]
```

The build stage installs dependencies and compiles TypeScript. The runtime stage copies only the compiled output and production `node_modules`.

This eliminates the entire class of "system package" vulnerabilities -- the build tools and their transitive dependencies never make it into the final image. The image drops from 1.2 GB to around 180 MB.

The worker gets a base image bump from `python:3.11-slim` to `python:3.11-slim-bookworm` with a pinned digest. The web-frontend gets an nginx version bump from 1.24 to 1.27, also pinned by digest. Both changes are single-line edits with no configuration changes needed.

### Step 4: Verify the Fixes

A re-scan after applying all changes confirms the results:

| Image | Before (Critical/High) | After (Critical/High) | Size Change |
|-------|------------------------|----------------------|-------------|
| `api-server:latest` | 3 / 12 | 0 / 1 (unfixable, no upstream patch) | 1.2 GB to 180 MB |
| `worker:latest` | 0 / 4 | 0 / 0 | 340 MB to 290 MB |
| `web-frontend:latest` | 1 / 2 | 0 / 0 | 45 MB to 42 MB |

The single remaining high-severity finding in api-server is in a system library with no upstream fix yet -- the maintainers have acknowledged the CVE but have not released a patch. It goes into a tracking list for monthly re-check with a documented risk acceptance: "CVE-XXXX in libfoo: no upstream patch available, not directly exploitable in our usage pattern, monitored monthly." When the upstream fix arrives, the base image will pick it up automatically on the next rebuild.

The size reductions are a bonus. The api-server went from 1.2 GB to 180 MB -- an 85% reduction. Smaller images mean faster pulls, faster deploys, and less storage cost. But the security benefit is the real win: fewer packages in the image means fewer things that can have vulnerabilities.

### Step 5: Add Scanning to the CI Pipeline

Fixing existing images is a one-time effort. Preventing new vulnerabilities from shipping requires continuous scanning:

```text
Add Trivy scanning to our CI pipeline. Fail builds on any critical vulnerability. Warn on high. Post results as a PR comment so developers see the findings during code review.
```

The CI integration scans every Docker image at build time, before it can be pushed to the container registry. Critical findings block the build. High findings post a warning comment on the PR with the specific CVE, affected package, and recommended fix. Developers see security findings during normal code review instead of months later during an audit.

The pipeline also pins base image digests in each Dockerfile and checks for newer base images weekly. When a base image update is available that resolves known CVEs, the pipeline opens a PR with the digest update. This prevents the "6-month-old base image" problem that caused most of the original findings -- base images stay current without anyone needing to remember to update them.

## Real-World Example

Soren applies all fixes in one afternoon. The re-scan shows zero critical CVEs across all 8 production images. The quarterly security audit passes with two weeks to spare.

But the real payoff is what happens next. Three weeks later, a developer adds a new dependency that pulls in a library with a known critical CVE. The CI pipeline catches it before the image reaches staging. The developer swaps in an alternative library, and the build passes cleanly. The whole interaction takes 20 minutes -- no Slack threads, no audit scramble, no emergency.

The team goes from "136 CVEs in a Slack thread nobody reads" to "zero critical vulnerabilities, caught at build time." The quarterly audit scramble is replaced by continuous verification that takes zero ongoing effort.
