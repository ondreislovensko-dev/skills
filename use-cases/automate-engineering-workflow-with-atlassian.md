---
title: Automate Engineering Workflow with Atlassian Stack
slug: automate-engineering-workflow-with-atlassian
description: "Build an integration layer that connects Jira, Confluence, and Bitbucket — auto-create Confluence RFCs from Jira epics, link PRs to issues, generate sprint reports, and sync deployment status across the stack."
skills: [jira, confluence, bitbucket]
category: project-management
tags: [jira, confluence, bitbucket, atlassian, automation, engineering, devops]
---

# Automate Engineering Workflow with Atlassian Stack

## The Problem

Nadia is a tech lead at a 35-person SaaS company using the full Atlassian stack — Jira for issue tracking, Confluence for docs, and Bitbucket for code. But nothing talks to each other beyond basic links. Engineers create Jira tickets, then manually create matching Confluence pages for RFCs, forget to link PRs, and sprint retrospective docs are copy-pasted from Jira. When code deploys, nobody updates the Jira ticket. She wants a middleware that automates the glue between all three tools.

## The Solution

Use the **jira**, **confluence**, and **bitbucket** skills to build a Node.js service that listens for webhooks from all three platforms and automates cross-tool workflows: RFC page creation, PR-to-issue linking, deployment status sync, and automated sprint reports.

## Step-by-Step Walkthrough

### 1. Define the requirements

```text
I need to automate our Atlassian workflow. We use Jira, Confluence, and Bitbucket Cloud on the same Atlassian site. Here's what I want:

1. RFC automation: When a Jira Epic is created with label "rfc", auto-create a Confluence page from our RFC template in the Engineering space, link it back to the Epic.
2. PR linking: When a Bitbucket PR is created with a Jira key in the branch name (e.g., feature/ENG-142-auth), auto-add the PR link to the Jira issue and transition it to "In Review".
3. Deploy tracking: When a Bitbucket Pipeline deploys to staging or production, update all Jira issues in that deployment with the environment and timestamp.
4. Sprint reports: When a sprint is completed in Jira, auto-generate a Confluence page with velocity stats, completed/incomplete issues, and carryover list.
5. Stale PR alerts: Daily check for PRs open > 3 days with no activity, post a comment tagging the author.

Build it as an Express server with webhook handlers.
```

### 2. Set up the project

```bash
mkdir atlassian-glue && cd atlassian-glue
npm init -y
npm install express node-cron
npm install -D typescript @types/node @types/express
npx tsc --init
```

```text
atlassian-glue/
├── src/
│   ├── index.ts           # Express server + webhook routes
│   ├── clients.ts         # Jira, Confluence, Bitbucket API clients
│   ├── flows/
│   │   ├── rfc.ts         # Epic → Confluence RFC page
│   │   ├── pr-link.ts     # PR → Jira issue linking
│   │   ├── deploy.ts      # Pipeline → Jira deploy status
│   │   ├── sprint-report.ts  # Sprint close → Confluence report
│   │   └── stale-prs.ts   # Daily stale PR check
│   └── templates.ts       # Confluence page templates
└── .env
```

### 3. Configure environment

```bash
# .env — single Atlassian site, one API token covers all three products.
ATLASSIAN_SITE=https://your-company.atlassian.net
ATLASSIAN_EMAIL=automation@company.com
ATLASSIAN_API_TOKEN=your_api_token

# Bitbucket uses separate auth (App Password)
BB_USERNAME=automation-bot
BB_APP_PASSWORD=your_app_password
BB_WORKSPACE=your-workspace

# Confluence space and Jira project
CONFLUENCE_SPACE_KEY=ENG
JIRA_PROJECT_KEY=ENG

# Webhook secret for signature verification
WEBHOOK_SECRET=your_webhook_secret
```

### 4. Build the API clients

```typescript
// src/clients.ts — Unified API clients for the Atlassian stack.
// One API token authenticates Jira + Confluence (same site).
// Bitbucket uses a separate App Password.

const SITE = process.env.ATLASSIAN_SITE!;
const ATLASSIAN_AUTH = Buffer.from(
  `${process.env.ATLASSIAN_EMAIL}:${process.env.ATLASSIAN_API_TOKEN}`
).toString("base64");
const BB_AUTH = Buffer.from(
  `${process.env.BB_USERNAME}:${process.env.BB_APP_PASSWORD}`
).toString("base64");

/** Jira Cloud REST API v3. */
export async function jira(method: string, path: string, body?: any) {
  const res = await fetch(`${SITE}/rest/api/3${path}`, {
    method,
    headers: {
      Authorization: `Basic ${ATLASSIAN_AUTH}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`Jira ${method} ${path}: ${res.status} ${await res.text()}`);
  return res.status === 204 ? null : res.json();
}

/** Jira Agile API (boards, sprints, ranking). */
export async function agile(method: string, path: string, body?: any) {
  const res = await fetch(`${SITE}/rest/agile/1.0${path}`, {
    method,
    headers: {
      Authorization: `Basic ${ATLASSIAN_AUTH}`,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`Agile ${method} ${path}: ${res.status}`);
  return res.json();
}

/** Confluence Cloud REST API v1 (templates, CQL, macros). */
export async function confluence(method: string, path: string, body?: any) {
  const res = await fetch(`${SITE}/wiki/rest/api${path}`, {
    method,
    headers: {
      Authorization: `Basic ${ATLASSIAN_AUTH}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`Confluence ${method} ${path}: ${res.status} ${await res.text()}`);
  return res.json();
}

/** Bitbucket Cloud REST API 2.0. */
export async function bb(method: string, path: string, body?: any) {
  const res = await fetch(`https://api.bitbucket.org/2.0${path}`, {
    method,
    headers: {
      Authorization: `Basic ${BB_AUTH}`,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`BB ${method} ${path}: ${res.status} ${await res.text()}`);
  return res.status === 204 ? null : res.json();
}
```

### 5. Build Flow 1: Epic → Confluence RFC Page

```typescript
// src/flows/rfc.ts — When a Jira Epic with label "rfc" is created,
// auto-create a Confluence RFC page from template and link it back.

import { jira, confluence } from "../clients";
import { rfcTemplate } from "../templates";

export async function handleEpicCreated(issue: any) {
  // Only trigger for Epics with the "rfc" label
  if (issue.fields.issuetype.name !== "Epic") return;
  if (!issue.fields.labels?.includes("rfc")) return;

  const epicKey = issue.key;
  const epicTitle = issue.fields.summary;
  const epicDesc = issue.fields.description;

  console.log(`[RFC] Creating Confluence page for ${epicKey}: ${epicTitle}`);

  // Find the RFCs parent page in the Engineering space
  const rfcParent = await confluence("GET",
    `/content?title=RFCs&spaceKey=${process.env.CONFLUENCE_SPACE_KEY}&type=page`
  );
  const parentId = rfcParent.results[0]?.id;
  if (!parentId) {
    console.error("[RFC] No 'RFCs' parent page found in Confluence space");
    return;
  }

  // Create the RFC page using our template
  const pageBody = rfcTemplate({
    title: epicTitle,
    epicKey,
    author: issue.fields.creator?.displayName || "Unknown",
    description: epicDesc,
  });

  const page = await confluence("POST", "/content", {
    type: "page",
    title: `RFC: ${epicTitle}`,
    space: { key: process.env.CONFLUENCE_SPACE_KEY },
    ancestors: [{ id: parentId }],
    body: { storage: { value: pageBody, representation: "storage" } },
    metadata: {
      properties: {
        "content-appearance-draft": {
          value: "full-width",
          key: "content-appearance-draft",
        },
      },
    },
  });

  // Add labels for organization
  await confluence("POST", `/content/${page.id}/label`, [
    { prefix: "global", name: "rfc" },
    { prefix: "global", name: epicKey.toLowerCase() },
  ]);

  // Link the Confluence page back to the Jira Epic
  // Add the page URL as a remote link on the Epic
  await jira("POST", `/issue/${epicKey}/remotelink`, {
    globalId: `confluence-${page.id}`,
    application: { type: "com.atlassian.confluence", name: "Confluence" },
    relationship: "RFC Document",
    object: {
      url: `${process.env.ATLASSIAN_SITE}/wiki/spaces/${process.env.CONFLUENCE_SPACE_KEY}/pages/${page.id}`,
      title: `RFC: ${epicTitle}`,
      icon: { url16x16: "https://confluence.atlassian.com/favicon.ico" },
    },
  });

  // Add a comment on the Epic with the link
  await jira("POST", `/issue/${epicKey}/comment`, {
    body: {
      type: "doc", version: 1,
      content: [{
        type: "paragraph",
        content: [
          { type: "text", text: "📝 RFC page created: " },
          {
            type: "text", text: `RFC: ${epicTitle}`,
            marks: [{
              type: "link",
              attrs: { href: `${process.env.ATLASSIAN_SITE}/wiki/spaces/${process.env.CONFLUENCE_SPACE_KEY}/pages/${page.id}` },
            }],
          },
        ],
      }],
    },
  });

  console.log(`[RFC] Created page ${page.id} and linked to ${epicKey}`);
}
```

### 6. Build Flow 2: PR → Jira Issue Linking

```typescript
// src/flows/pr-link.ts — When a Bitbucket PR is created with a Jira key
// in the branch name (e.g., feature/ENG-142-auth), auto-link the PR
// to the Jira issue and transition it to "In Review".

import { jira } from "../clients";

// Regex to extract Jira issue keys from branch names
const JIRA_KEY_PATTERN = /([A-Z]+-\d+)/g;

export async function handlePRCreated(payload: any) {
  const pr = payload.pullrequest;
  const branchName = pr.source.branch.name;
  const prTitle = pr.title;
  const prUrl = pr.links.html.href;
  const authorName = pr.author.display_name;

  // Extract all Jira keys from branch name and PR title
  const keysFromBranch = branchName.match(JIRA_KEY_PATTERN) || [];
  const keysFromTitle = prTitle.match(JIRA_KEY_PATTERN) || [];
  const issueKeys = [...new Set([...keysFromBranch, ...keysFromTitle])];

  if (issueKeys.length === 0) {
    console.log(`[PR-Link] No Jira keys found in branch "${branchName}" or title`);
    return;
  }

  for (const issueKey of issueKeys) {
    try {
      console.log(`[PR-Link] Linking PR #${pr.id} to ${issueKey}`);

      // Add the PR as a remote link on the Jira issue
      await jira("POST", `/issue/${issueKey}/remotelink`, {
        globalId: `bitbucket-pr-${pr.id}`,
        application: { type: "com.atlassian.bitbucket", name: "Bitbucket" },
        relationship: "Pull Request",
        object: {
          url: prUrl,
          title: `PR #${pr.id}: ${prTitle}`,
          icon: { url16x16: "https://bitbucket.org/favicon.ico" },
          status: {
            resolved: false,
            icon: { url16x16: "https://bitbucket.org/favicon.ico", title: "Open" },
          },
        },
      });

      // Transition the issue to "In Review" (if that status exists)
      const transitions = await jira("GET", `/issue/${issueKey}/transitions`);
      const inReview = transitions.transitions.find(
        (t: any) => t.name.toLowerCase().includes("review")
      );

      if (inReview) {
        await jira("POST", `/issue/${issueKey}/transitions`, {
          transition: { id: inReview.id },
        });
        console.log(`[PR-Link] ${issueKey} → In Review`);
      }

      // Add a comment with PR details
      await jira("POST", `/issue/${issueKey}/comment`, {
        body: {
          type: "doc", version: 1,
          content: [{
            type: "paragraph",
            content: [
              { type: "text", text: `🔀 Pull Request opened by ${authorName}: ` },
              {
                type: "text", text: `#${pr.id} ${prTitle}`,
                marks: [{ type: "link", attrs: { href: prUrl } }],
              },
            ],
          }],
        },
      });
    } catch (e: any) {
      console.error(`[PR-Link] Error linking to ${issueKey}: ${e.message}`);
    }
  }
}
```

### 7. Build Flow 3: Deployment → Jira Status Update

```typescript
// src/flows/deploy.ts — When a Bitbucket Pipeline completes a deployment,
// find all Jira issues in that deployment (from commit messages) and
// update them with the deployment environment and timestamp.

import { jira, bb } from "../clients";

const JIRA_KEY_PATTERN = /([A-Z]+-\d+)/g;

export async function handlePipelineCompleted(payload: any) {
  const pipeline = payload.commit_status;
  if (!pipeline) return;

  // Only process successful deployments
  if (pipeline.state !== "SUCCESSFUL") return;

  const repoSlug = pipeline.repository.full_name;
  const pipelineUrl = pipeline.url;

  // Determine environment from pipeline name or deployment
  let environment = "unknown";
  const name = (pipeline.name || "").toLowerCase();
  if (name.includes("production") || name.includes("prod")) environment = "production";
  else if (name.includes("staging") || name.includes("stage")) environment = "staging";
  else if (name.includes("test") || name.includes("dev")) environment = "development";
  else return; // Skip non-deployment pipelines

  console.log(`[Deploy] ${environment} deployment completed for ${repoSlug}`);

  // Get commits in this pipeline to find Jira keys
  const commits = await bb("GET",
    `/repositories/${repoSlug}/commits?pagelen=20`
  );

  // Collect unique Jira keys from recent commit messages
  const issueKeys = new Set<string>();
  for (const commit of commits.values.slice(0, 20)) {
    const keys = commit.message.match(JIRA_KEY_PATTERN) || [];
    keys.forEach((k: string) => issueKeys.add(k));
  }

  if (issueKeys.size === 0) {
    console.log("[Deploy] No Jira keys found in recent commits");
    return;
  }

  console.log(`[Deploy] Updating ${issueKeys.size} Jira issues with ${environment} deploy status`);

  const timestamp = new Date().toISOString();

  for (const issueKey of issueKeys) {
    try {
      // Update custom fields with deployment info
      // (These custom field IDs vary per Jira instance — find yours via /field endpoint)
      await jira("PUT", `/issue/${issueKey}`, {
        fields: {
          // Example custom fields — adjust IDs to your instance
          customfield_10100: environment,     // "Deployed To" field
          customfield_10101: timestamp,       // "Last Deploy Date" field
        },
      });

      // Add a comment documenting the deployment
      const envEmoji = environment === "production" ? "🚀" : "🧪";
      await jira("POST", `/issue/${issueKey}/comment`, {
        body: {
          type: "doc", version: 1,
          content: [{
            type: "paragraph",
            content: [
              { type: "text", text: `${envEmoji} Deployed to ` },
              { type: "text", text: environment, marks: [{ type: "strong" }] },
              { type: "text", text: ` at ${new Date().toLocaleString()}` },
            ],
          }],
        },
      });

      // If deploying to production, transition to "Done"
      if (environment === "production") {
        const transitions = await jira("GET", `/issue/${issueKey}/transitions`);
        const done = transitions.transitions.find(
          (t: any) => t.name === "Done"
        );
        if (done) {
          await jira("POST", `/issue/${issueKey}/transitions`, {
            transition: { id: done.id },
          });
        }
      }
    } catch (e: any) {
      console.error(`[Deploy] Error updating ${issueKey}: ${e.message}`);
    }
  }
}
```

### 8. Build Flow 4: Sprint Close → Confluence Report

```typescript
// src/flows/sprint-report.ts — When a sprint is completed in Jira,
// auto-generate a Confluence page with velocity stats, completed issues,
// incomplete issues, and carryover list.

import { jira, agile, confluence } from "../clients";

export async function generateSprintReport(sprintId: number, boardId: number) {
  console.log(`[Sprint Report] Generating report for sprint ${sprintId}`);

  // Get sprint details
  const sprint = await agile("GET", `/sprint/${sprintId}`);

  // Get all issues that were in this sprint
  const issues = await agile("GET",
    `/sprint/${sprintId}/issue?maxResults=200&fields=summary,status,assignee,customfield_10016,issuetype,priority`
  );

  // Separate completed vs incomplete
  const completed = issues.issues.filter(
    (i: any) => i.fields.status.statusCategory.key === "done"
  );
  const incomplete = issues.issues.filter(
    (i: any) => i.fields.status.statusCategory.key !== "done"
  );

  // Calculate velocity (total story points completed)
  const pointsCompleted = completed.reduce(
    (sum: number, i: any) => sum + (i.fields.customfield_10016 || 0), 0
  );
  const pointsPlanned = issues.issues.reduce(
    (sum: number, i: any) => sum + (i.fields.customfield_10016 || 0), 0
  );

  // Get historical velocity (last 5 sprints) for comparison
  const closedSprints = await agile("GET",
    `/board/${boardId}/sprint?state=closed&maxResults=6`
  );
  const velocityHistory: number[] = [];
  for (const s of closedSprints.values.slice(0, 5)) {
    const sIssues = await agile("GET",
      `/sprint/${s.id}/issue?fields=customfield_10016,status`
    );
    const pts = sIssues.issues
      .filter((i: any) => i.fields.status.statusCategory.key === "done")
      .reduce((sum: number, i: any) => sum + (i.fields.customfield_10016 || 0), 0);
    velocityHistory.push(pts);
  }
  const avgVelocity = velocityHistory.length > 0
    ? Math.round(velocityHistory.reduce((a, b) => a + b, 0) / velocityHistory.length)
    : 0;

  // Build Confluence page content
  const issueRows = (items: any[]) => items.map((i: any) => `
    <tr>
      <td><a href="${process.env.ATLASSIAN_SITE}/browse/${i.key}">${i.key}</a></td>
      <td>${escapeHtml(i.fields.summary)}</td>
      <td>${i.fields.issuetype.name}</td>
      <td>${i.fields.priority.name}</td>
      <td>${i.fields.assignee?.displayName || "Unassigned"}</td>
      <td>${i.fields.customfield_10016 || "-"}</td>
      <td>${i.fields.status.name}</td>
    </tr>
  `).join("");

  const pageBody = `
    <ac:structured-macro ac:name="info">
      <ac:rich-text-body>
        <p>Auto-generated sprint report for <strong>${escapeHtml(sprint.name)}</strong>
        (${sprint.startDate?.split("T")[0]} → ${sprint.endDate?.split("T")[0]})</p>
      </ac:rich-text-body>
    </ac:structured-macro>

    <h2>📊 Summary</h2>
    <table>
      <tr><td><strong>Sprint Goal</strong></td><td>${escapeHtml(sprint.goal || "No goal set")}</td></tr>
      <tr><td><strong>Velocity</strong></td><td>${pointsCompleted} / ${pointsPlanned} story points (${Math.round(pointsCompleted / pointsPlanned * 100)}% completion)</td></tr>
      <tr><td><strong>5-Sprint Average</strong></td><td>${avgVelocity} points</td></tr>
      <tr><td><strong>Issues Completed</strong></td><td>${completed.length} of ${issues.issues.length}</td></tr>
      <tr><td><strong>Carryover</strong></td><td>${incomplete.length} issues (${pointsPlanned - pointsCompleted} points)</td></tr>
    </table>

    <h2>✅ Completed (${completed.length})</h2>
    <table>
      <tr><th>Key</th><th>Summary</th><th>Type</th><th>Priority</th><th>Assignee</th><th>Points</th><th>Status</th></tr>
      ${issueRows(completed)}
    </table>

    <h2>🔄 Carryover (${incomplete.length})</h2>
    <table>
      <tr><th>Key</th><th>Summary</th><th>Type</th><th>Priority</th><th>Assignee</th><th>Points</th><th>Status</th></tr>
      ${issueRows(incomplete)}
    </table>

    <h2>📈 Velocity Trend</h2>
    <p>Last 5 sprints: ${velocityHistory.map((v, i) =>
      `Sprint ${closedSprints.values[i]?.name || i}: ${v} pts`
    ).join(" → ")}</p>
  `;

  // Find Sprint Reports parent page
  const parentSearch = await confluence("GET",
    `/content?title=Sprint Reports&spaceKey=${process.env.CONFLUENCE_SPACE_KEY}&type=page`
  );
  const parentId = parentSearch.results[0]?.id;

  // Create the report page
  const page = await confluence("POST", "/content", {
    type: "page",
    title: `${sprint.name} Report — ${new Date().toISOString().split("T")[0]}`,
    space: { key: process.env.CONFLUENCE_SPACE_KEY },
    ancestors: parentId ? [{ id: parentId }] : [],
    body: { storage: { value: pageBody, representation: "storage" } },
  });

  // Label it for easy discovery
  await confluence("POST", `/content/${page.id}/label`, [
    { prefix: "global", name: "sprint-report" },
    { prefix: "global", name: sprint.name.toLowerCase().replace(/\s+/g, "-") },
  ]);

  console.log(`[Sprint Report] Created: ${page.title} (${page.id})`);
  return page;
}

function escapeHtml(text: string): string {
  if (!text) return "";
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
```

### 9. Build Flow 5: Stale PR Check (Daily Cron)

```typescript
// src/flows/stale-prs.ts — Daily check for PRs open > 3 days with no activity.
// Posts a reminder comment tagging the author.

import { bb } from "../clients";

export async function checkStalePRs() {
  const workspace = process.env.BB_WORKSPACE!;
  const repos = await bb("GET", `/repositories/${workspace}?pagelen=100`);

  let staleCount = 0;
  const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000);

  for (const repo of repos.values) {
    const prs = await bb("GET",
      `/repositories/${workspace}/${repo.slug}/pullrequests?state=OPEN&pagelen=50`
    );

    for (const pr of prs.values) {
      const updatedAt = new Date(pr.updated_on);

      // Skip PRs that have been updated recently
      if (updatedAt > threeDaysAgo) continue;

      const daysSinceUpdate = Math.floor(
        (Date.now() - updatedAt.getTime()) / (1000 * 60 * 60 * 24)
      );

      console.log(
        `[Stale PR] ${repo.slug}#${pr.id}: "${pr.title}" — ` +
        `${daysSinceUpdate} days since last update`
      );

      // Post a reminder comment
      await bb("POST",
        `/repositories/${workspace}/${repo.slug}/pullrequests/${pr.id}/comments`, {
          content: {
            raw: `⏰ This PR has had no activity for ${daysSinceUpdate} days. ` +
              `@${pr.author.nickname} — is this still in progress, or should it be closed?`,
          },
        }
      );
      staleCount++;
    }
  }

  console.log(`[Stale PR] Found ${staleCount} stale PRs across ${repos.values.length} repos`);
}
```

### 10. Wire up the server

```typescript
// src/index.ts — Express server with webhook handlers for all three Atlassian products.

import express from "express";
import cron from "node-cron";
import { handleEpicCreated } from "./flows/rfc";
import { handlePRCreated } from "./flows/pr-link";
import { handlePipelineCompleted } from "./flows/deploy";
import { generateSprintReport } from "./flows/sprint-report";
import { checkStalePRs } from "./flows/stale-prs";

const app = express();
app.use(express.json());

// --- Jira webhook: issue events ---
app.post("/webhook/jira", async (req, res) => {
  res.sendStatus(200);
  const { webhookEvent, issue, sprint } = req.body;

  try {
    if (webhookEvent === "jira:issue_created") {
      await handleEpicCreated(issue);
    }
    if (webhookEvent === "sprint_closed" && sprint) {
      // Sprint closed — generate Confluence report
      // boardId is in the sprint's originBoardId field
      await generateSprintReport(sprint.id, sprint.originBoardId);
    }
  } catch (e: any) {
    console.error(`[Jira Webhook] Error: ${e.message}`);
  }
});

// --- Bitbucket webhook: PR and pipeline events ---
app.post("/webhook/bitbucket", async (req, res) => {
  res.sendStatus(200);
  const event = req.headers["x-event-key"];

  try {
    if (event === "pullrequest:created") {
      await handlePRCreated(req.body);
    }
    if (event === "repo:commit_status_updated") {
      await handlePipelineCompleted(req.body);
    }
  } catch (e: any) {
    console.error(`[BB Webhook] Error: ${e.message}`);
  }
});

// --- Daily stale PR check at 9:00 AM ---
cron.schedule("0 9 * * 1-5", async () => {
  console.log("[Cron] Running stale PR check...");
  await checkStalePRs();
});

// --- Health check ---
app.get("/health", (req, res) => {
  res.json({ status: "ok", uptime: process.uptime() });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Atlassian Glue running on port ${PORT}`);
  console.log("Webhook endpoints:");
  console.log("  POST /webhook/jira");
  console.log("  POST /webhook/bitbucket");
});
```

Five workflows, one server. Epics auto-create RFC docs, PRs link themselves to tickets, deployments update issue status, sprint close generates a full report in Confluence, and stale PRs get daily reminders — all without engineers touching three different tools manually.
