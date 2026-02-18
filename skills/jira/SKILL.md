---
name: jira
description: >-
  Manage projects, issues, and workflows with Jira Cloud. Use when a user asks
  to set up Jira projects, create and manage issues, configure workflows, build
  Jira integrations, automate issue transitions, set up boards (Scrum/Kanban),
  manage sprints, use Jira REST API v3, create webhooks, build custom JQL
  queries, configure permissions and schemes, set up automation rules, or
  integrate Jira with CI/CD pipelines. Covers project administration, issue
  tracking, agile boards, API automation, and Atlassian Connect/Forge apps.
license: Apache-2.0
compatibility: "Node.js 18+ or any HTTP client (REST API v3)"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: project-management
  tags: ["jira", "atlassian", "project-management", "issue-tracker", "agile", "scrum", "kanban"]
---

# Jira

## Overview

Automate and extend Jira Cloud — the most widely used issue tracker and project management tool. This skill covers project setup, issue CRUD, workflow configuration, Scrum and Kanban boards, sprint management, JQL (Jira Query Language) for advanced searches, REST API v3 for automation, webhooks, and building Atlassian Forge apps.

## Instructions

### Step 1: Authentication

Jira Cloud uses API tokens for basic auth or OAuth 2.0 (3LO) for apps:

```typescript
// Basic auth with API token — simplest option for scripts and integrations.
// Generate a token at: https://id.atlassian.com/manage-profile/security/api-tokens

const JIRA_BASE = "https://your-domain.atlassian.net";
const AUTH = Buffer.from(`your-email@company.com:${process.env.JIRA_API_TOKEN}`).toString("base64");

async function jira(method: string, path: string, body?: any) {
  const res = await fetch(`${JIRA_BASE}/rest/api/3${path}`, {
    method,
    headers: {
      Authorization: `Basic ${AUTH}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Jira ${method} ${path}: ${res.status} ${err}`);
  }
  return res.status === 204 ? null : res.json();
}
```

```typescript
// OAuth 2.0 (3LO) for Atlassian Connect apps — required for Marketplace apps.
// Register at: https://developer.atlassian.com/console/myapps/

const OAUTH_CONFIG = {
  clientId: process.env.ATLASSIAN_CLIENT_ID!,
  clientSecret: process.env.ATLASSIAN_CLIENT_SECRET!,
  redirectUri: "https://your-app.com/callback",
  scopes: [
    "read:jira-work",      // Read issues, projects, boards
    "write:jira-work",     // Create/update issues
    "manage:jira-project", // Admin: workflows, schemes, permissions
    "manage:jira-configuration", // Site-level configuration
  ],
};

// Step 1: Redirect user to Atlassian authorization
function getAuthUrl(): string {
  const params = new URLSearchParams({
    audience: "api.atlassian.com",
    client_id: OAUTH_CONFIG.clientId,
    scope: OAUTH_CONFIG.scopes.join(" "),
    redirect_uri: OAUTH_CONFIG.redirectUri,
    response_type: "code",
    prompt: "consent",
  });
  return `https://auth.atlassian.com/authorize?${params}`;
}

// Step 2: Exchange authorization code for tokens
async function exchangeCode(code: string) {
  const res = await fetch("https://auth.atlassian.com/oauth/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      grant_type: "authorization_code",
      client_id: OAUTH_CONFIG.clientId,
      client_secret: OAUTH_CONFIG.clientSecret,
      code,
      redirect_uri: OAUTH_CONFIG.redirectUri,
    }),
  });
  return res.json(); // { access_token, refresh_token, expires_in, scope }
}
```

### Step 2: Projects & Issue Types

Create and configure projects with issue type schemes:

```typescript
// Create a Scrum software project.
// projectTypeKey options: "software" (Scrum/Kanban), "business", "service_desk"
const project = await jira("POST", "/project", {
  key: "ENG",                        // 2-10 char uppercase key for issue prefixes (ENG-1, ENG-2)
  name: "Engineering",
  projectTypeKey: "software",
  leadAccountId: "5f1234abc...",     // Atlassian account ID of the project lead
  description: "Core product engineering",
  assigneeType: "UNASSIGNED",       // Default assignee: PROJECT_LEAD or UNASSIGNED
});

// Get all issue types available in the project
const issueTypes = await jira("GET", `/project/${project.key}/statuses`);
// Default software types: Epic, Story, Task, Bug, Sub-task

// Create a custom issue type (requires admin permissions)
const customType = await jira("POST", "/issuetype", {
  name: "Tech Debt",
  description: "Technical debt item requiring refactoring",
  type: "standard",    // "standard" or "subtask"
  hierarchyLevel: 0,   // 0 = same level as Story/Task, -1 = Epic level
});
```

### Step 3: Issues — CRUD & Bulk Operations

```typescript
// Create an issue with all common fields.
// Fields vary by project and issue type — use /issue/createmeta for discovery.
const issue = await jira("POST", "/issue", {
  fields: {
    project: { key: "ENG" },
    issuetype: { name: "Story" },
    summary: "Implement user authentication flow",
    description: {
      // Jira Cloud uses Atlassian Document Format (ADF), not plain text
      type: "doc",
      version: 1,
      content: [{
        type: "paragraph",
        content: [{
          type: "text",
          text: "Build OAuth2 login with Google and GitHub providers. Include MFA support.",
        }],
      }],
    },
    priority: { name: "High" },              // Highest, High, Medium, Low, Lowest
    labels: ["auth", "security"],
    assignee: { accountId: "5f1234abc..." },
    reporter: { accountId: "5f5678def..." },
    // Story points (custom field — ID varies per instance)
    customfield_10016: 8,
    // Sprint (custom field — assign to active sprint)
    customfield_10020: 42,
    // Epic link (custom field)
    customfield_10014: "ENG-100",
    components: [{ name: "Backend" }],
    fixVersions: [{ name: "v2.1" }],
  },
});
console.log(`Created: ${issue.key}`); // e.g., ENG-142

// Transition an issue through the workflow (e.g., "To Do" → "In Progress")
// First, get available transitions for the current state
const transitions = await jira("GET", `/issue/${issue.key}/transitions`);
// Find the transition ID for "In Progress"
const inProgressTransition = transitions.transitions.find(
  (t: any) => t.name === "In Progress"
);
await jira("POST", `/issue/${issue.key}/transitions`, {
  transition: { id: inProgressTransition.id },
  fields: {
    assignee: { accountId: "5f1234abc..." }, // Optionally set fields during transition
  },
  update: {
    comment: [{                              // Add a comment with the transition
      add: {
        body: {
          type: "doc", version: 1,
          content: [{ type: "paragraph", content: [{ type: "text", text: "Starting work on this." }] }],
        },
      },
    }],
  },
});

// Bulk create issues (up to 50 per request)
const bulkResult = await jira("POST", "/issue/bulk", {
  issueUpdates: [
    { fields: { project: { key: "ENG" }, issuetype: { name: "Task" }, summary: "Set up CI pipeline" } },
    { fields: { project: { key: "ENG" }, issuetype: { name: "Task" }, summary: "Configure staging env" } },
    { fields: { project: { key: "ENG" }, issuetype: { name: "Bug" }, summary: "Fix login timeout on Safari", priority: { name: "High" } } },
  ],
});
// bulkResult.issues = [{ id, key, self }, ...]
// bulkResult.errors = [] (any that failed)
```

### Step 4: JQL — Jira Query Language

```typescript
// JQL is Jira's powerful query language for searching and filtering issues.
// Results are paginated — use startAt and maxResults for large sets.

// Find high-priority bugs assigned to me in the current sprint
const myBugs = await jira("POST", "/search", {
  jql: `project = ENG
    AND issuetype = Bug
    AND priority in (High, Highest)
    AND assignee = currentUser()
    AND sprint in openSprints()
    ORDER BY priority DESC, created ASC`,
  maxResults: 50,
  startAt: 0,
  fields: ["summary", "status", "priority", "assignee", "created"],
});

// Unresolved issues older than 30 days (stale work detection)
const staleIssues = await jira("POST", "/search", {
  jql: `project = ENG
    AND status != Done
    AND created <= -30d
    AND updated <= -14d
    ORDER BY updated ASC`,
  maxResults: 100,
  fields: ["summary", "status", "assignee", "updated"],
});

// Issues changed in the last 24 hours (activity feed)
const recentActivity = await jira("POST", "/search", {
  jql: `project = ENG AND updated >= -1d ORDER BY updated DESC`,
  maxResults: 50,
  fields: ["summary", "status", "assignee", "updated"],
  expand: ["changelog"], // Include change history
});

// Useful JQL functions reference:
// currentUser()           — logged-in user
// membersOf("team-name")  — users in a group
// openSprints()           — active sprints
// futureSprints()         — planned sprints
// startOfDay(), endOfWeek(), startOfMonth(-1) — relative dates
// issueHistory()          — issues the user has viewed
```

### Step 5: Boards & Sprints (Agile API)

```typescript
// The Agile API is separate from the core API — different base path.
async function agile(method: string, path: string, body?: any) {
  const res = await fetch(`${JIRA_BASE}/rest/agile/1.0${path}`, {
    method,
    headers: {
      Authorization: `Basic ${AUTH}`,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`Agile ${method} ${path}: ${res.status}`);
  return res.json();
}

// Get all boards
const boards = await agile("GET", "/board?type=scrum");

// Get active sprint for a board
const sprints = await agile("GET", `/board/${boardId}/sprint?state=active`);
const activeSprint = sprints.values[0];

// Get all issues in the active sprint
const sprintIssues = await agile("GET",
  `/sprint/${activeSprint.id}/issue?fields=summary,status,assignee,customfield_10016`
);

// Create a new sprint
const newSprint = await agile("POST", "/sprint", {
  name: "Sprint 24",
  startDate: "2026-02-24T09:00:00.000Z",
  endDate: "2026-03-07T17:00:00.000Z",
  originBoardId: boardId,
  goal: "Complete auth module and API v2 migration",
});

// Move issues to a sprint
await agile("POST", `/sprint/${newSprint.id}/issue`, {
  issues: ["ENG-142", "ENG-143", "ENG-144"],
});

// Complete a sprint (moves unfinished issues to backlog or next sprint)
await agile("POST", `/sprint/${activeSprint.id}`, {
  state: "closed",
  completeDate: new Date().toISOString(),
});

// Get the board's backlog
const backlog = await agile("GET", `/board/${boardId}/backlog`);

// Rank/reorder issues on the board
await agile("PUT", "/issue/rank", {
  issues: ["ENG-150"],
  rankBeforeIssue: "ENG-142", // Place ENG-150 before ENG-142
});
```

### Step 6: Workflows & Automation

```typescript
// Get all workflows in the instance
const workflows = await jira("GET", "/workflow/search?expand=statuses,transitions");

// Automation rules via REST (Jira Automation is typically configured in UI,
// but you can trigger rules via webhooks or smart values)

// Example: Auto-transition linked issues when an Epic is marked Done.
// Register a webhook to listen for issue updates:
const webhook = await jira("POST", "/webhook", {
  name: "Epic completion handler",
  url: "https://your-app.com/webhook/jira",
  events: ["jira:issue_updated"],
  filters: {
    "issue-related-events-section": `project = ENG AND issuetype = Epic`,
  },
});

// Webhook handler: when Epic → Done, transition all child issues to Done
app.post("/webhook/jira", async (req, res) => {
  res.sendStatus(200);
  const { issue, changelog } = req.body;

  // Check if status changed to "Done"
  const statusChange = changelog?.items?.find(
    (item: any) => item.field === "status" && item.toString === "Done"
  );
  if (!statusChange || issue.fields.issuetype.name !== "Epic") return;

  // Find all issues in this Epic
  const children = await jira("POST", "/search", {
    jql: `"Epic Link" = ${issue.key} AND status != Done`,
    fields: ["status"],
  });

  // Transition each child to Done
  for (const child of children.issues) {
    const transitions = await jira("GET", `/issue/${child.key}/transitions`);
    const doneTransition = transitions.transitions.find(
      (t: any) => t.name === "Done"
    );
    if (doneTransition) {
      await jira("POST", `/issue/${child.key}/transitions`, {
        transition: { id: doneTransition.id },
      });
    }
  }
});
```

### Step 7: Dashboards & Reporting

```typescript
// Get velocity data for a board (story points completed per sprint)
const velocityReport = await agile("GET", `/board/${boardId}/properties/velocity`);

// Build a custom burndown by querying sprint issues with changelog
const sprintIssuesWithHistory = await agile("GET",
  `/sprint/${sprintId}/issue?expand=changelog&fields=customfield_10016,status,resolutiondate`
);

// Calculate velocity from completed sprints
async function getVelocity(boardId: number, sprintCount = 5) {
  const closedSprints = await agile("GET",
    `/board/${boardId}/sprint?state=closed&maxResults=${sprintCount}`
  );

  const velocities = [];
  for (const sprint of closedSprints.values) {
    const issues = await agile("GET",
      `/sprint/${sprint.id}/issue?fields=customfield_10016,status`
    );
    const completed = issues.issues
      .filter((i: any) => i.fields.status.statusCategory.key === "done")
      .reduce((sum: number, i: any) => sum + (i.fields.customfield_10016 || 0), 0);
    velocities.push({ sprint: sprint.name, points: completed });
  }
  return velocities;
}

// Create a dashboard filter (saved JQL query visible to the team)
const filter = await jira("POST", "/filter", {
  name: "Sprint Burndown - ENG",
  jql: "project = ENG AND sprint in openSprints() ORDER BY rank ASC",
  sharePermissions: [{ type: "project", project: { id: project.id } }],
});
```

### Step 8: Permissions & Schemes

```typescript
// Get permission scheme for a project
const scheme = await jira("GET", `/project/${projectKey}/permissionscheme`);

// Check if the current user has a specific permission
const permission = await jira("GET",
  `/mypermissions?projectKey=ENG&permissions=EDIT_ISSUES,ASSIGN_ISSUES`
);
// permission.permissions.EDIT_ISSUES.havePermission = true/false

// Add a user to a project role
await jira("POST", `/project/${projectKey}/role/${roleId}`, {
  user: ["accountId1", "accountId2"],
});

// Common roles:
// 10002 = Administrators
// 10001 = Developers  (default for software projects)
// 10000 = Users
```
