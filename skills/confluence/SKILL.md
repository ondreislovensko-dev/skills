---
name: confluence
description: >-
  Manage knowledge bases and documentation with Confluence Cloud. Use when a
  user asks to create or manage Confluence spaces, pages, and blogs, build
  documentation systems, automate page creation from templates, use Confluence
  REST API v2, manage page trees and hierarchies, set up permissions, integrate
  Confluence with Jira or other tools, generate reports from Confluence data,
  build macros or Forge apps, or migrate content between spaces. Covers content
  management, API automation, templates, and Atlassian ecosystem integration.
license: Apache-2.0
compatibility: "Node.js 18+ or any HTTP client (REST API v2)"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: documentation
  tags: ["confluence", "atlassian", "documentation", "wiki", "knowledge-base", "collaboration"]
---

# Confluence

## Overview

Automate and extend Confluence Cloud — Atlassian's wiki and knowledge management platform. This skill covers space and page management, the REST API v2, content creation with Atlassian Document Format (ADF), page trees, templates, labels, permissions, Jira integration, and building Forge apps.

## Instructions

### Step 1: Authentication

Same as Jira — API tokens for basic auth or OAuth 2.0 for apps:

```typescript
// Basic auth with API token.
// Same token works for both Jira and Confluence on the same Atlassian site.
const CONFLUENCE_BASE = "https://your-domain.atlassian.net";
const AUTH = Buffer.from(
  `your-email@company.com:${process.env.ATLASSIAN_API_TOKEN}`
).toString("base64");

// Confluence REST API v2 — newer, cleaner than v1
async function confluence(method: string, path: string, body?: any) {
  const res = await fetch(`${CONFLUENCE_BASE}/wiki/api/v2${path}`, {
    method,
    headers: {
      Authorization: `Basic ${AUTH}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`Confluence ${method} ${path}: ${res.status} ${await res.text()}`);
  return res.status === 204 ? null : res.json();
}

// V1 API still needed for some operations (templates, macros, CQL search)
async function confluenceV1(method: string, path: string, body?: any) {
  const res = await fetch(`${CONFLUENCE_BASE}/wiki/rest/api${path}`, {
    method,
    headers: {
      Authorization: `Basic ${AUTH}`,
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`Confluence V1 ${method} ${path}: ${res.status}`);
  return res.json();
}
```

### Step 2: Spaces

```typescript
// Create a space — the top-level container for pages.
// Each space has a unique key (uppercase, 2-10 chars).
const space = await confluence("POST", "/spaces", {
  key: "ENG",
  name: "Engineering",
  description: {
    plain: { value: "Engineering team documentation, RFCs, and runbooks", representation: "plain" },
  },
  type: "global",   // "global" (visible to all) or "personal"
});

// List all spaces with pagination
const spaces = await confluence("GET", "/spaces?limit=25&sort=name");

// Get a specific space with homepage
const engSpace = await confluence("GET", "/spaces/ENG?include-homepage=true");

// Update space settings
await confluence("PUT", `/spaces/${space.id}`, {
  name: "Engineering Docs",
  description: {
    plain: { value: "Updated description", representation: "plain" },
  },
});
```

### Step 3: Pages — CRUD & Hierarchy

```typescript
// Create a page in the space root.
// Body uses Atlassian Document Format (ADF) or legacy "storage" format (XHTML).
const page = await confluence("POST", "/pages", {
  spaceId: space.id,
  status: "current",           // "current" (published) or "draft"
  title: "API Design Guidelines",
  body: {
    representation: "storage",  // "storage" = Confluence XHTML, simpler than ADF for basic pages
    value: `
      <h2>REST API Conventions</h2>
      <p>All APIs must follow these conventions:</p>
      <ul>
        <li>Use plural nouns for resource paths: <code>/users</code>, <code>/orders</code></li>
        <li>Version via URL prefix: <code>/v1/users</code></li>
        <li>Return 201 for creation, 204 for deletion</li>
        <li>Use HATEOAS links in responses</li>
      </ul>
      <ac:structured-macro ac:name="info">
        <ac:rich-text-body>
          <p>These guidelines apply to all public-facing APIs starting Q1 2026.</p>
        </ac:rich-text-body>
      </ac:structured-macro>
    `,
  },
});

// Create a child page (nested under a parent)
const childPage = await confluence("POST", "/pages", {
  spaceId: space.id,
  parentId: page.id,           // This makes it a child of the API Design Guidelines page
  title: "Authentication Standards",
  body: {
    representation: "storage",
    value: "<p>All APIs use OAuth 2.0 with JWT bearer tokens.</p>",
  },
});

// Update a page — MUST include the current version number
const currentPage = await confluence("GET", `/pages/${page.id}?body-format=storage`);
await confluence("PUT", `/pages/${page.id}`, {
  id: page.id,
  status: "current",
  title: "API Design Guidelines v2",
  body: {
    representation: "storage",
    value: "<p>Updated content...</p>",
  },
  version: {
    number: currentPage.version.number + 1,   // Must increment by 1
    message: "Added error handling section",   // Version comment
  },
});

// Get the full page tree (all descendants of a page)
const descendants = await confluence("GET",
  `/pages/${page.id}/children?limit=50&sort=title`
);

// Move a page to a different parent
await confluence("PUT", `/pages/${childPage.id}`, {
  id: childPage.id,
  status: "current",
  title: childPage.title,
  parentId: newParentId,       // Reparent the page
  version: { number: childPage.version.number + 1, message: "Moved to new section" },
});

// Delete a page (moves to trash, recoverable for 30 days)
await confluence("DELETE", `/pages/${page.id}`);
```

### Step 4: CQL — Confluence Query Language

```typescript
// CQL is Confluence's search language — similar to JQL but for content.
// Uses the V1 API (CQL not available in V2 yet).

// Search for pages containing specific text
const results = await confluenceV1("GET",
  `/content/search?cql=${encodeURIComponent(
    'type = page AND space = "ENG" AND text ~ "authentication" ORDER BY lastModified DESC'
  )}&limit=20`
);

// Find recently updated pages in a space
const recent = await confluenceV1("GET",
  `/content/search?cql=${encodeURIComponent(
    'type = page AND space = "ENG" AND lastModified >= now("-7d") ORDER BY lastModified DESC'
  )}&limit=50`
);

// Find pages with a specific label
const labeled = await confluenceV1("GET",
  `/content/search?cql=${encodeURIComponent(
    'type = page AND label = "runbook" AND space = "ENG"'
  )}&limit=50`
);

// Find pages created by a specific user
const userPages = await confluenceV1("GET",
  `/content/search?cql=${encodeURIComponent(
    'type = page AND creator = "5f1234abc..." ORDER BY created DESC'
  )}&limit=20`
);
```

### Step 5: Labels & Organization

```typescript
// Add labels to a page (for categorization and search)
await confluenceV1("POST", `/content/${page.id}/label`, [
  { prefix: "global", name: "runbook" },
  { prefix: "global", name: "production" },
  { prefix: "global", name: "auth" },
]);

// Get all labels on a page
const labels = await confluenceV1("GET", `/content/${page.id}/label`);

// Remove a label
await confluenceV1("DELETE", `/content/${page.id}/label/runbook`);

// Find all pages with a given label across all spaces
const allRunbooks = await confluenceV1("GET",
  `/content/search?cql=${encodeURIComponent('label = "runbook"')}&limit=100`
);
```

### Step 6: Templates

```typescript
// Create a reusable page template (blueprint).
// Templates use storage format with variables for placeholders.
const template = await confluenceV1("POST", "/template", {
  name: "Incident Postmortem",
  templateType: "page",
  description: "Standard template for production incident postmortems",
  space: { key: "ENG" },
  body: {
    storage: {
      value: `
        <h2>Incident Summary</h2>
        <ac:structured-macro ac:name="panel">
          <ac:parameter ac:name="title">Quick Facts</ac:parameter>
          <ac:rich-text-body>
            <ul>
              <li><strong>Severity:</strong> <at:var at:name="severity">P1/P2/P3</at:var></li>
              <li><strong>Duration:</strong> <at:var at:name="duration">X hours</at:var></li>
              <li><strong>Services Affected:</strong> <at:var at:name="services">list services</at:var></li>
              <li><strong>Incident Commander:</strong> <at:var at:name="commander">name</at:var></li>
            </ul>
          </ac:rich-text-body>
        </ac:structured-macro>
        <h2>Timeline</h2>
        <p>Chronological list of events...</p>
        <h2>Root Cause</h2>
        <p>What caused this incident...</p>
        <h2>Action Items</h2>
        <ac:structured-macro ac:name="tasklist">
          <ac:rich-text-body>
            <ac:task><ac:task-body>Action item 1</ac:task-body></ac:task>
            <ac:task><ac:task-body>Action item 2</ac:task-body></ac:task>
          </ac:rich-text-body>
        </ac:structured-macro>
      `,
      representation: "storage",
    },
  },
});

// Create a page from a template
const fromTemplate = await confluenceV1("POST", "/content", {
  type: "page",
  title: "Postmortem: Auth Service Outage 2026-02-18",
  space: { key: "ENG" },
  ancestors: [{ id: postmortemsParentPageId }],
  metadata: {
    properties: {
      "content-appearance-draft": { value: "full-width", key: "content-appearance-draft" },
    },
  },
  body: {
    storage: {
      value: template.body.storage.value
        .replace("P1/P2/P3", "P1")
        .replace("X hours", "2 hours 15 minutes")
        .replace("list services", "Auth API, User Service, Admin Panel"),
      representation: "storage",
    },
  },
});
```

### Step 7: Attachments & Media

```typescript
// Upload a file attachment to a page
const fs = require("fs");
const FormData = require("form-data");

const form = new FormData();
form.append("file", fs.createReadStream("architecture-diagram.png"));
form.append("comment", "Updated system architecture diagram");

const attachment = await fetch(
  `${CONFLUENCE_BASE}/wiki/rest/api/content/${page.id}/child/attachment`,
  {
    method: "PUT",  // PUT creates or updates; POST always creates new
    headers: {
      Authorization: `Basic ${AUTH}`,
      "X-Atlassian-Token": "nocheck", // Required for file uploads
      ...form.getHeaders(),
    },
    body: form,
  }
).then(r => r.json());

// List all attachments on a page
const attachments = await confluenceV1("GET",
  `/content/${page.id}/child/attachment?limit=50`
);

// Download an attachment
const downloadUrl = `${CONFLUENCE_BASE}/wiki/download/attachments/${page.id}/${encodeURIComponent("architecture-diagram.png")}`;
```

### Step 8: Permissions

```typescript
// Get page restrictions (who can view/edit)
const restrictions = await confluenceV1("GET",
  `/content/${page.id}/restriction`
);

// Restrict editing to specific users
await confluenceV1("PUT", `/content/${page.id}/restriction`, [{
  operation: "update",
  restrictions: {
    user: [
      { type: "known", accountId: "5f1234abc..." },
      { type: "known", accountId: "5f5678def..." },
    ],
    group: [
      { type: "group", name: "engineering-leads" },
    ],
  },
}]);

// Set space permissions
await confluence("POST", `/spaces/${space.id}/permissions`, {
  subject: { type: "group", identifier: "engineering" },
  operation: { key: "read", target: "space" },
});
```

### Step 9: Webhooks & Events

```typescript
// Register a webhook for content events
const webhook = await fetch(`${CONFLUENCE_BASE}/wiki/rest/api/webhooks`, {
  method: "POST",
  headers: {
    Authorization: `Basic ${AUTH}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    name: "Page update notifier",
    url: "https://your-app.com/webhook/confluence",
    events: [
      "page_created",
      "page_updated",
      "page_removed",
      "comment_created",
    ],
    active: true,
  }),
}).then(r => r.json());

// Webhook handler
app.post("/webhook/confluence", (req, res) => {
  res.sendStatus(200);
  const event = req.body;
  // event.eventType = "page_created" | "page_updated" | ...
  // event.page = { id, title, space, version, ... }
  console.log(`${event.eventType}: ${event.page?.title || "unknown"}`);
});
```

### Step 10: Jira Integration

```typescript
// Embed Jira issues in Confluence pages using the Jira macro.
// This renders a live table of Jira issues inside the Confluence page.
const pageWithJira = await confluenceV1("POST", "/content", {
  type: "page",
  title: "Sprint 24 Status",
  space: { key: "ENG" },
  body: {
    storage: {
      value: `
        <h2>Current Sprint Issues</h2>
        <p>Live view of Sprint 24 progress:</p>
        <ac:structured-macro ac:name="jira">
          <ac:parameter ac:name="server">System JIRA</ac:parameter>
          <ac:parameter ac:name="jqlQuery">project = ENG AND sprint = "Sprint 24" ORDER BY priority DESC</ac:parameter>
          <ac:parameter ac:name="columns">key,summary,status,assignee,priority</ac:parameter>
          <ac:parameter ac:name="maximumIssues">50</ac:parameter>
        </ac:structured-macro>
        <h2>Burndown</h2>
        <p>Check the <a href="${CONFLUENCE_BASE}/jira/software/projects/ENG/boards/1">Scrum board</a> for the live burndown chart.</p>
      `,
      representation: "storage",
    },
  },
});
```
