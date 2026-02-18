---
name: clickup
description: >-
  Automate and integrate with ClickUp. Use when a user asks to manage tasks,
  lists, and spaces via the ClickUp API, build automations and webhooks,
  create custom fields, set up time tracking, manage sprints and goals,
  integrate ClickUp with external tools, build dashboards, automate task
  assignments, sync with GitHub or Slack, or extend ClickUp with custom
  workflows. Covers API v2, webhooks, custom fields, automations, and
  reporting.
license: Apache-2.0
compatibility: "Any HTTP client or Node.js 18+ (ClickUp API v2, REST)"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: project-management
  tags: ["clickup", "project-management", "task-management", "automation", "api", "webhooks"]
---

# ClickUp

## Overview

Automate and extend ClickUp — the all-in-one productivity platform. This skill covers the full ClickUp API v2 for managing workspaces, spaces, folders, lists, and tasks programmatically. Includes webhooks for real-time events, custom fields, time tracking, goals, automations, and integration patterns with GitHub, Slack, and CI/CD pipelines.

## Instructions

### Step 1: Authentication & API Setup

Get an API token from ClickUp → Settings → Apps → API Token (personal), or create an OAuth2 app for multi-user integrations.

**Personal token:**
```bash
export CLICKUP_API_TOKEN="pk_xxxxxxxxxxxxxxxxxxxx"
```

**Test the connection:**
```bash
curl -s https://api.clickup.com/api/v2/user \
  -H "Authorization: $CLICKUP_API_TOKEN" | python3 -m json.tool
```

**Response:**
```json
{
  "user": {
    "id": 12345678,
    "username": "dev@company.com",
    "email": "dev@company.com",
    "color": "#7B68EE"
  }
}
```

**Helper module** (Node.js):
```typescript
const BASE = "https://api.clickup.com/api/v2";
const TOKEN = process.env.CLICKUP_API_TOKEN;

async function clickup(method: string, path: string, body?: any) {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      Authorization: TOKEN!,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json();
}
```

**OAuth2 flow** (for apps serving multiple users):
```typescript
// 1. Redirect user to authorize
const authUrl = `https://app.clickup.com/api?client_id=${CLIENT_ID}&redirect_uri=${REDIRECT_URI}`;

// 2. Exchange code for token
const tokenRes = await fetch("https://api.clickup.com/api/v2/oauth/token", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    client_id: CLIENT_ID,
    client_secret: CLIENT_SECRET,
    code: authCode,
  }),
});
const { access_token } = await tokenRes.json();
```

### Step 2: Workspace Hierarchy

ClickUp's hierarchy: **Workspace → Spaces → Folders → Lists → Tasks → Subtasks**.

**List workspaces (teams):**
```bash
curl -s https://api.clickup.com/api/v2/team \
  -H "Authorization: $CLICKUP_API_TOKEN"
```

**List spaces in a workspace:**
```typescript
const spaces = await clickup("GET", `/team/${teamId}/space?archived=false`);
for (const space of spaces.spaces) {
  console.log(`${space.name} (${space.id}) — ${space.statuses.map((s: any) => s.status).join(", ")}`);
}
```

**Create a space:**
```typescript
const space = await clickup("POST", `/team/${teamId}/space`, {
  name: "Engineering",
  multiple_assignees: true,
  features: {
    due_dates: { enabled: true, start_date: true, remap_due_dates: true, remap_closed_due_date: false },
    time_tracking: { enabled: true },
    tags: { enabled: true },
    time_estimates: { enabled: true },
    checklists: { enabled: true },
    custom_fields: { enabled: true },
    remap_dependencies: { enabled: true },
    dependency_warning: { enabled: true },
    portfolios: { enabled: true },
    milestones: { enabled: true },
    sprint_management: { enabled: true },
  },
});
```

**Create a folder:**
```typescript
const folder = await clickup("POST", `/space/${spaceId}/folder`, {
  name: "Q1 2026 Roadmap",
});
```

**Create a list:**
```typescript
const list = await clickup("POST", `/folder/${folderId}/list`, {
  name: "Sprint 14",
  content: "Feb 17 — Mar 2, 2026",
  due_date: 1772524800000, // Unix ms
  priority: 2,
  status: "active",
});
```

**Folderless list** (directly in a space):
```typescript
const list = await clickup("POST", `/space/${spaceId}/list`, {
  name: "Backlog",
});
```

### Step 3: Tasks — CRUD & Bulk Operations

**Create a task:**
```typescript
const task = await clickup("POST", `/list/${listId}/task`, {
  name: "Implement OAuth2 login",
  description: "Add Google and GitHub OAuth2 providers.\n\n## Acceptance Criteria\n- [ ] Google login works\n- [ ] GitHub login works\n- [ ] Existing users can link accounts",
  assignees: [userId1, userId2],
  tags: ["backend", "auth"],
  status: "to do",
  priority: 2, // 1=urgent, 2=high, 3=normal, 4=low
  due_date: 1772524800000,
  start_date: 1771315200000,
  time_estimate: 28800000, // 8 hours in ms
  notify_all: true,
  links_to: null,
  check_required_custom_fields: true,
  custom_fields: [
    { id: "custom_field_id", value: "frontend" },
  ],
});
console.log(`Created: ${task.id} — ${task.url}`);
```

**Get tasks with filters:**
```typescript
const tasks = await clickup("GET",
  `/list/${listId}/task?` + new URLSearchParams({
    archived: "false",
    page: "0",
    order_by: "due_date",
    statuses: ["in progress", "review"].join(","),
    assignees: [userId].join(","),
    include_closed: "false",
    subtasks: "true",
  }).toString()
);
```

**Update a task:**
```typescript
await clickup("PUT", `/task/${taskId}`, {
  name: "Updated task name",
  status: "in progress",
  priority: 1,
  assignees: { add: [newUserId], rem: [oldUserId] },
});
```

**Create subtasks:**
```typescript
const subtask = await clickup("POST", `/list/${listId}/task`, {
  name: "Write unit tests for OAuth module",
  parent: parentTaskId,
  assignees: [userId],
  priority: 3,
});
```

**Add a comment:**
```typescript
await clickup("POST", `/task/${taskId}/comment`, {
  comment_text: "Blocked by the auth provider outage. Resuming tomorrow.",
  assignee: userId,
  notify_all: false,
});
```

**Add a checklist:**
```typescript
const checklist = await clickup("POST", `/task/${taskId}/checklist`, {
  name: "Deployment Checklist",
});

const items = ["Run migrations", "Smoke test staging", "Update docs", "Tag release"];
for (const item of items) {
  await clickup("POST", `/checklist/${checklist.checklist.id}/checklist_item`, {
    name: item,
  });
}
```

**Set dependencies:**
```typescript
await clickup("POST", `/task/${taskId}/dependency`, {
  depends_on: blockingTaskId,
  // or: dependency_of: dependentTaskId
});
```

**Bulk task operations** (filter + batch update):
```typescript
// Move all "to do" tasks from old list to new list
const oldTasks = await clickup("GET", `/list/${oldListId}/task?statuses[]=to%20do`);

for (const task of oldTasks.tasks) {
  await clickup("PUT", `/task/${task.id}`, { list: newListId });
}
console.log(`Moved ${oldTasks.tasks.length} tasks`);
```

### Step 4: Custom Fields

**Create a custom field on a list:**
```typescript
// Via API — custom fields are typically created in the UI,
// then referenced by ID in the API
const list = await clickup("GET", `/list/${listId}`);

// Get custom field definitions for a list
const fields = await clickup("GET", `/list/${listId}/field`);
for (const field of fields.fields) {
  console.log(`${field.name} (${field.id}) — type: ${field.type}`);
}
```

**Set custom field values on a task:**
```typescript
// Dropdown field
await clickup("POST", `/task/${taskId}/field/${dropdownFieldId}`, {
  value: "option_uuid", // UUID of the dropdown option
});

// Number field
await clickup("POST", `/task/${taskId}/field/${numberFieldId}`, {
  value: 42,
});

// Text field
await clickup("POST", `/task/${taskId}/field/${textFieldId}`, {
  value: "Custom text value",
});

// Date field
await clickup("POST", `/task/${taskId}/field/${dateFieldId}`, {
  value: 1772524800000, // Unix ms
});

// Labels/tags field
await clickup("POST", `/task/${taskId}/field/${labelFieldId}`, {
  value: ["option_uuid_1", "option_uuid_2"],
});
```

**Filter tasks by custom field:**
```typescript
const filtered = await clickup("GET",
  `/list/${listId}/task?custom_fields=[{"field_id":"${fieldId}","operator":"=","value":"${value}"}]`
);
```

### Step 5: Time Tracking

**Start a timer:**
```typescript
await clickup("POST", `/task/${taskId}/time`, {
  start: Date.now(),
  end: Date.now() + 3600000, // 1 hour
  time: 3600000,
  billable: true,
  tags: [{ name: "development" }],
});
```

**Get time entries for a task:**
```typescript
const entries = await clickup("GET", `/task/${taskId}/time`);
const totalMs = entries.data.reduce((sum: number, e: any) => sum + parseInt(e.duration), 0);
console.log(`Total tracked: ${(totalMs / 3600000).toFixed(1)} hours`);
```

**Get time entries for a date range (workspace-wide):**
```typescript
const entries = await clickup("GET",
  `/team/${teamId}/time_entries?` + new URLSearchParams({
    start_date: String(Date.now() - 7 * 86400000), // Last 7 days
    end_date: String(Date.now()),
    assignee: String(userId),
  }).toString()
);
```

**Running timer:**
```typescript
// Get current running timer
const running = await clickup("GET", `/team/${teamId}/time_entries/current?assignee=${userId}`);

// Stop running timer
if (running.data) {
  await clickup("POST", `/team/${teamId}/time_entries/stop`, {
    tid: running.data.id,
  });
}
```

### Step 6: Goals & Targets

**Create a goal:**
```typescript
const goal = await clickup("POST", `/team/${teamId}/goal`, {
  name: "Reduce P1 bug count by 50%",
  due_date: 1772524800000,
  description: "Q1 target: bring critical bugs from 24 to under 12",
  multiple_owners: true,
  owners: [userId1, userId2],
  color: "#ef4444",
});
```

**Add key results (targets):**
```typescript
await clickup("POST", `/goal/${goalId}/key_result`, {
  name: "P1 bugs resolved",
  type: "number",
  steps_start: 0,
  steps_end: 12,
  unit: "bugs",
  owners: [userId],
});

await clickup("POST", `/goal/${goalId}/key_result`, {
  name: "Automated test coverage",
  type: "percentage",
  steps_start: 45,
  steps_end: 80,
  owners: [userId2],
});

// Task-based target (auto-tracks task completion)
await clickup("POST", `/goal/${goalId}/key_result`, {
  name: "Complete security audit tasks",
  type: "automatic",
  list_ids: [securityListId],
  owners: [userId],
});
```

**Update target progress:**
```typescript
await clickup("PUT", `/key_result/${keyResultId}`, {
  steps_current: 8, // 8 out of 12 bugs resolved
  note: "Fixed 3 more this week",
});
```

### Step 7: Webhooks

**Create a webhook:**
```typescript
const webhook = await clickup("POST", `/team/${teamId}/webhook`, {
  endpoint: "https://your-server.com/clickup/webhook",
  events: [
    "taskCreated",
    "taskUpdated",
    "taskDeleted",
    "taskStatusUpdated",
    "taskAssigneeUpdated",
    "taskPriorityUpdated",
    "taskCommentPosted",
    "taskTimeTrackedUpdated",
    "taskMoved",
    "taskDueDateUpdated",
  ],
  space_id: spaceId,     // Optional: scope to space
  folder_id: folderId,   // Optional: scope to folder
  list_id: listId,       // Optional: scope to list
  task_id: taskId,        // Optional: scope to single task
});
console.log(`Webhook ID: ${webhook.id}`);
```

**Webhook payload structure:**
```json
{
  "event": "taskStatusUpdated",
  "webhook_id": "webhook-uuid",
  "task_id": "task-id",
  "history_items": [
    {
      "id": "history-id",
      "type": 1,
      "date": "1708272000000",
      "field": "status",
      "parent_id": "task-id",
      "before": { "status": "to do", "color": "#d3d3d3", "type": "open" },
      "after": { "status": "in progress", "color": "#4194f6", "type": "custom" },
      "user": { "id": 12345, "username": "dev@company.com" }
    }
  ]
}
```

**Webhook handler** (Express):
```typescript
import express from "express";
import crypto from "crypto";

const app = express();
app.use(express.json());

app.post("/clickup/webhook", async (req, res) => {
  // Verify webhook signature
  const signature = req.headers["x-signature"];
  const hmac = crypto.createHmac("sha256", process.env.CLICKUP_WEBHOOK_SECRET!);
  hmac.update(JSON.stringify(req.body));
  if (hmac.digest("hex") !== signature) return res.sendStatus(401);

  res.sendStatus(200);

  const { event, task_id, history_items } = req.body;

  switch (event) {
    case "taskStatusUpdated": {
      const change = history_items[0];
      const newStatus = change.after.status;
      console.log(`Task ${task_id} → ${newStatus}`);

      // Auto-assign reviewer when moved to "review"
      if (newStatus === "review") {
        await clickup("PUT", `/task/${task_id}`, {
          assignees: { add: [reviewerUserId] },
        });
        // Notify Slack
        await notifySlack(`🔍 Task ready for review: ${task_id}`);
      }
      break;
    }

    case "taskPriorityUpdated": {
      const change = history_items[0];
      if (change.after.priority === "1") { // Urgent
        await notifySlack(`🚨 Urgent task: ${task_id}`);
      }
      break;
    }

    case "taskCreated": {
      console.log(`New task: ${task_id}`);
      break;
    }
  }
});
```

**List and manage webhooks:**
```typescript
// List
const webhooks = await clickup("GET", `/team/${teamId}/webhook`);

// Update
await clickup("PUT", `/webhook/${webhookId}`, {
  endpoint: "https://new-url.com/webhook",
  events: ["taskCreated", "taskUpdated"],
  status: "active", // or "inactive"
});

// Delete
await clickup("DELETE", `/webhook/${webhookId}`);
```

### Step 8: Views & Reporting

**Get all views for a space:**
```typescript
const views = await clickup("GET", `/space/${spaceId}/view`);
for (const view of views.views) {
  console.log(`${view.name} (${view.id}) — type: ${view.type}`);
}
```

**Get tasks from a view** (includes filters/sorting):
```typescript
const viewTasks = await clickup("GET", `/view/${viewId}/task?page=0`);
```

**Build a velocity report** (tasks completed per sprint list):
```typescript
async function velocityReport(sprintListIds: string[]) {
  const results = [];
  for (const listId of sprintListIds) {
    const list = await clickup("GET", `/list/${listId}`);
    const tasks = await clickup("GET", `/list/${listId}/task?include_closed=true`);
    const completed = tasks.tasks.filter((t: any) => t.status.type === "closed");
    const totalEstimate = tasks.tasks.reduce((s: number, t: any) => s + (t.time_estimate || 0), 0);
    const completedEstimate = completed.reduce((s: number, t: any) => s + (t.time_estimate || 0), 0);

    results.push({
      sprint: list.name,
      total: tasks.tasks.length,
      completed: completed.length,
      completionRate: Math.round((completed.length / tasks.tasks.length) * 100),
      estimatedHours: Math.round(totalEstimate / 3600000),
      completedHours: Math.round(completedEstimate / 3600000),
    });
  }
  return results;
}
```

**Time tracking report by member:**
```typescript
async function teamTimeReport(teamId: string, startDate: number, endDate: number) {
  const entries = await clickup("GET",
    `/team/${teamId}/time_entries?start_date=${startDate}&end_date=${endDate}`
  );

  const byUser: Record<string, { total: number; billable: number; tasks: Set<string> }> = {};

  for (const entry of entries.data) {
    const user = entry.user.username;
    if (!byUser[user]) byUser[user] = { total: 0, billable: 0, tasks: new Set() };
    byUser[user].total += parseInt(entry.duration);
    if (entry.billable) byUser[user].billable += parseInt(entry.duration);
    byUser[user].tasks.add(entry.task.id);
  }

  for (const [user, data] of Object.entries(byUser)) {
    console.log(`${user}: ${(data.total / 3600000).toFixed(1)}h total, ${(data.billable / 3600000).toFixed(1)}h billable, ${data.tasks.size} tasks`);
  }
}
```

### Step 9: Integrations

**GitHub integration** (auto-link PRs to tasks):

Include the task ID in branch names or PR titles:
```
git checkout -b feature/CU-abc123-oauth-login
# PR title: "feat: OAuth login [CU-abc123]"
```

ClickUp's native GitHub integration auto-links when it detects `CU-` prefixed IDs.

**Slack notifications via webhook handler:**
```typescript
async function notifySlack(text: string, channel = "#engineering") {
  await fetch(process.env.SLACK_WEBHOOK_URL!, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ channel, text }),
  });
}
```

**Sync ClickUp tasks to a database** (for custom dashboards):
```typescript
async function syncTasksToDb(listId: string, db: any) {
  let page = 0;
  let hasMore = true;

  while (hasMore) {
    const res = await clickup("GET", `/list/${listId}/task?page=${page}&include_closed=true&subtasks=true`);
    for (const task of res.tasks) {
      await db.upsert("tasks", {
        id: task.id,
        name: task.name,
        status: task.status.status,
        priority: task.priority?.id,
        assignees: task.assignees.map((a: any) => a.username),
        due_date: task.due_date,
        time_estimate: task.time_estimate,
        time_spent: task.time_spent,
        date_created: task.date_created,
        date_updated: task.date_updated,
        date_closed: task.date_closed,
        list_id: listId,
        custom_fields: task.custom_fields,
        url: task.url,
      });
    }
    hasMore = !res.last_page;
    page++;
  }
}
```

**Create tasks from CI/CD failures:**
```yaml
# GitHub Actions — create ClickUp task on test failure
name: Create ClickUp bug on failure
on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]

jobs:
  create-bug:
    if: github.event.workflow_run.conclusion == 'failure'
    runs-on: ubuntu-latest
    steps:
      - name: Create ClickUp task
        run: |
          curl -X POST "https://api.clickup.com/api/v2/list/${{ secrets.CLICKUP_BUG_LIST_ID }}/task" \
            -H "Authorization: ${{ secrets.CLICKUP_API_TOKEN }}" \
            -H "Content-Type: application/json" \
            -d '{
              "name": "[CI] Build failure: ${{ github.event.workflow_run.head_branch }}",
              "description": "CI pipeline failed.\n\nBranch: ${{ github.event.workflow_run.head_branch }}\nCommit: ${{ github.event.workflow_run.head_sha }}\nRun: ${{ github.event.workflow_run.html_url }}",
              "priority": 2,
              "tags": ["ci-failure", "bug"],
              "assignees": [${{ secrets.CLICKUP_ONCALL_USER_ID }}]
            }'
```
