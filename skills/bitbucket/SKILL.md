---
name: bitbucket
description: >-
  Manage repositories, pipelines, and code review with Bitbucket Cloud. Use
  when a user asks to set up Bitbucket repositories, configure Bitbucket
  Pipelines for CI/CD, manage pull requests, set up branch permissions, use
  Bitbucket REST API 2.0, create webhooks, manage deployment environments,
  set up code review workflows, integrate with Jira, configure merge checks,
  or automate repository operations. Covers repository management, CI/CD
  pipelines, code review, deployments, and Atlassian ecosystem integration.
license: Apache-2.0
compatibility: "Node.js 18+ or any HTTP client (REST API 2.0)"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: devops
  tags: ["bitbucket", "atlassian", "git", "ci-cd", "pipelines", "code-review", "devops"]
---

# Bitbucket

## Overview

Automate and extend Bitbucket Cloud — Atlassian's Git platform with built-in CI/CD. This skill covers repository management, Bitbucket Pipelines configuration, pull request workflows, branch permissions, deployment environments, the REST API 2.0, webhooks, Jira integration, and merge checks.

## Instructions

### Step 1: Authentication

```typescript
// Bitbucket Cloud uses App Passwords (basic auth) or OAuth 2.0.
// Create an App Password at: https://bitbucket.org/account/settings/app-passwords/

const BB_BASE = "https://api.bitbucket.org/2.0";
const AUTH = Buffer.from(
  `${process.env.BB_USERNAME}:${process.env.BB_APP_PASSWORD}`
).toString("base64");

async function bb(method: string, path: string, body?: any) {
  const res = await fetch(`${BB_BASE}${path}`, {
    method,
    headers: {
      Authorization: `Basic ${AUTH}`,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`BB ${method} ${path}: ${res.status} ${await res.text()}`);
  return res.status === 204 ? null : res.json();
}

// OAuth 2.0 Consumer for apps (register at workspace settings)
async function getOAuthToken() {
  const res = await fetch("https://bitbucket.org/site/oauth2/access_token", {
    method: "POST",
    headers: {
      Authorization: "Basic " + Buffer.from(
        `${process.env.BB_OAUTH_KEY}:${process.env.BB_OAUTH_SECRET}`
      ).toString("base64"),
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: "grant_type=client_credentials",
  });
  return res.json(); // { access_token, token_type, expires_in, scopes }
}
```

### Step 2: Repositories

```typescript
// Create a repository in a workspace
const repo = await bb("POST", `/repositories/my-workspace/my-new-repo`, {
  scm: "git",
  is_private: true,
  description: "Backend API service",
  language: "typescript",
  has_issues: false,          // Use Jira instead
  has_wiki: false,            // Use Confluence instead
  project: { key: "ENG" },   // Bitbucket project (groups repos)
  mainbranch: { name: "main" },
  fork_policy: "no_public_forks", // "allow_forks" | "no_public_forks" | "no_forks"
});

// List repositories in a workspace with filters
const repos = await bb("GET",
  `/repositories/my-workspace?q=project.key="ENG"&sort=-updated_on&pagelen=25`
);

// Get repository details
const repoInfo = await bb("GET", `/repositories/my-workspace/my-repo`);

// List branches
const branches = await bb("GET",
  `/repositories/my-workspace/my-repo/refs/branches?sort=-target.date&pagelen=25`
);

// Get a specific file's content from a branch
const fileContent = await fetch(
  `${BB_BASE}/repositories/my-workspace/my-repo/src/main/README.md`,
  { headers: { Authorization: `Basic ${AUTH}` } }
).then(r => r.text());

// Browse the repository file tree
const srcTree = await bb("GET",
  `/repositories/my-workspace/my-repo/src/main/?pagelen=100`
);
```

### Step 3: Pull Requests

```typescript
// Create a pull request
const pr = await bb("POST", `/repositories/my-workspace/my-repo/pullrequests`, {
  title: "feat: add user authentication module",
  description: "Implements OAuth2 login with Google and GitHub.\n\n## Changes\n- Added auth middleware\n- JWT token generation\n- Session management\n\nCloses ENG-142",  // Jira key auto-links
  source: { branch: { name: "feature/auth" } },
  destination: { branch: { name: "main" } },
  close_source_branch: true,   // Delete branch after merge
  reviewers: [
    { account_id: "5f1234abc..." },  // Required reviewer
  ],
});

// List open pull requests
const openPRs = await bb("GET",
  `/repositories/my-workspace/my-repo/pullrequests?state=OPEN&pagelen=50`
);

// Approve a pull request
await bb("POST", `/repositories/my-workspace/my-repo/pullrequests/${pr.id}/approve`);

// Request changes
await bb("POST", `/repositories/my-workspace/my-repo/pullrequests/${pr.id}/request-changes`);

// Add a comment to a PR
await bb("POST", `/repositories/my-workspace/my-repo/pullrequests/${pr.id}/comments`, {
  content: { raw: "Looks good overall! One suggestion on the token expiry logic — see inline comment." },
});

// Add an inline comment on a specific file and line
await bb("POST", `/repositories/my-workspace/my-repo/pullrequests/${pr.id}/comments`, {
  content: { raw: "Consider using `crypto.timingSafeEqual` here to prevent timing attacks." },
  inline: {
    path: "src/auth/jwt.ts",
    to: 42,            // Line number in the new file
  },
});

// Merge a pull request
await bb("POST", `/repositories/my-workspace/my-repo/pullrequests/${pr.id}/merge`, {
  type: "pullrequest",
  merge_strategy: "squash",    // "merge_commit" | "squash" | "fast_forward"
  message: "feat: add user authentication module (#142)",
  close_source_branch: true,
});

// Decline (reject) a pull request
await bb("POST", `/repositories/my-workspace/my-repo/pullrequests/${pr.id}/decline`);
```

### Step 4: Branch Permissions & Merge Checks

```typescript
// Branch permissions restrict who can push/merge to protected branches.
// Requires Premium plan.

// Protect the main branch — require PR with 2 approvals, no direct pushes
await bb("POST",
  `/repositories/my-workspace/my-repo/branch-restrictions`, {
    kind: "require_approvals_to_merge",
    pattern: "main",            // Branch pattern (supports glob: release/*)
    value: 2,                   // Minimum number of approvals
  }
);

// Prevent direct pushes to main (force all changes through PRs)
await bb("POST",
  `/repositories/my-workspace/my-repo/branch-restrictions`, {
    kind: "push",
    pattern: "main",
    users: [],                  // Empty = nobody can push directly
    groups: [],
  }
);

// Require passing builds before merge
await bb("POST",
  `/repositories/my-workspace/my-repo/branch-restrictions`, {
    kind: "require_passing_builds_to_merge",
    pattern: "main",
    value: 1,                   // At least 1 passing build
  }
);

// Require all tasks resolved before merge
await bb("POST",
  `/repositories/my-workspace/my-repo/branch-restrictions`, {
    kind: "require_tasks_to_be_completed",
    pattern: "main",
  }
);

// List all branch restrictions
const restrictions = await bb("GET",
  `/repositories/my-workspace/my-repo/branch-restrictions`
);
```

### Step 5: Bitbucket Pipelines (CI/CD)

```yaml
# bitbucket-pipelines.yml — CI/CD configuration.
# Pipelines run in Docker containers with pre-installed build tools.

image: node:20-slim   # Base Docker image for all steps

definitions:
  # Reusable step definitions
  steps:
    - step: &test
        name: Test
        caches: [node]
        script:
          - npm ci
          - npm run lint
          - npm run test:coverage
        artifacts:
          - coverage/**    # Pass coverage reports to later steps
    - step: &build
        name: Build
        caches: [node]
        script:
          - npm ci
          - npm run build
        artifacts:
          - dist/**

pipelines:
  # Run on every push to any branch
  default:
    - step: *test

  # Branch-specific pipelines
  branches:
    main:
      - step: *test
      - step: *build
      - step:
          name: Deploy to Production
          deployment: production    # Links to deployment environment
          trigger: manual           # Require manual approval for prod
          script:
            - pipe: atlassian/aws-ecs-deploy:1.0.0
              variables:
                AWS_ACCESS_KEY_ID: $AWS_ACCESS_KEY_ID
                AWS_SECRET_ACCESS_KEY: $AWS_SECRET_ACCESS_KEY
                AWS_DEFAULT_REGION: "eu-west-1"
                CLUSTER_NAME: "prod-cluster"
                SERVICE_NAME: "api-service"
                TASK_DEFINITION: "task-def.json"

    develop:
      - step: *test
      - step: *build
      - step:
          name: Deploy to Staging
          deployment: staging
          script:
            - ./deploy.sh staging

  # Run on pull requests (merge checks)
  pull-requests:
    '**':              # All PR branches
      - step: *test

  # Custom pipelines (triggered manually or via API)
  custom:
    run-migrations:
      - step:
          name: Run Database Migrations
          script:
            - npm ci
            - npm run db:migrate
          after-script:
            - echo "Migration status: $BITBUCKET_EXIT_CODE"
```

```typescript
// Trigger a custom pipeline via API
const pipeline = await bb("POST",
  `/repositories/my-workspace/my-repo/pipelines/`, {
    target: {
      type: "pipeline_ref_target",
      ref_type: "branch",
      ref_name: "main",
      selector: {
        type: "custom",
        pattern: "run-migrations",   // Matches the custom pipeline name
      },
    },
    variables: [
      { key: "MIGRATION_TARGET", value: "v2.1.0", secured: false },
    ],
  }
);

// Get pipeline status
const pipelineStatus = await bb("GET",
  `/repositories/my-workspace/my-repo/pipelines/${pipeline.uuid}`
);
// pipelineStatus.state.name = "PENDING" | "IN_PROGRESS" | "COMPLETED"
// pipelineStatus.state.result.name = "SUCCESSFUL" | "FAILED" | "STOPPED"

// List recent pipelines
const pipelines = await bb("GET",
  `/repositories/my-workspace/my-repo/pipelines/?sort=-created_on&pagelen=10`
);

// Get pipeline step logs
const steps = await bb("GET",
  `/repositories/my-workspace/my-repo/pipelines/${pipeline.uuid}/steps/`
);
for (const step of steps.values) {
  const log = await fetch(
    `${BB_BASE}/repositories/my-workspace/my-repo/pipelines/${pipeline.uuid}/steps/${step.uuid}/log`,
    { headers: { Authorization: `Basic ${AUTH}` } }
  ).then(r => r.text());
  console.log(`[${step.name}]`, log);
}
```

### Step 6: Deployment Environments

```typescript
// Create deployment environments for tracking where code is running.
// Environments appear in the Deployments dashboard.

const environment = await bb("POST",
  `/repositories/my-workspace/my-repo/environments/`, {
    type: "deployment_environment",
    name: "Production",
    environment_type: {
      type: "deployment_environment_type",
      name: "Production",     // "Test" | "Staging" | "Production"
    },
  }
);

// List deployments
const deployments = await bb("GET",
  `/repositories/my-workspace/my-repo/deployments/?pagelen=20`
);

// Environment variables (secrets for pipelines)
await bb("POST",
  `/repositories/my-workspace/my-repo/pipelines_config/variables/`, {
    key: "AWS_ACCESS_KEY_ID",
    value: "AKIA...",
    secured: true,    // Encrypted, never shown in logs
  }
);

// Deployment-specific variables (different values per environment)
await bb("POST",
  `/repositories/my-workspace/my-repo/deployments_config/environments/${environment.uuid}/variables`, {
    key: "API_URL",
    value: "https://api.production.example.com",
    secured: false,
  }
);
```

### Step 7: Webhooks & Jira Integration

```typescript
// Register a webhook for repository events
const webhook = await bb("POST",
  `/repositories/my-workspace/my-repo/hooks`, {
    description: "CI/CD event handler",
    url: "https://your-app.com/webhook/bitbucket",
    active: true,
    events: [
      "repo:push",                    // Code pushed
      "pullrequest:created",          // New PR
      "pullrequest:approved",         // PR approved
      "pullrequest:fulfilled",        // PR merged
      "pullrequest:comment_created",  // PR comment
    ],
  }
);

// Webhook handler
app.post("/webhook/bitbucket", (req, res) => {
  res.sendStatus(200);
  const event = req.headers["x-event-key"];
  const payload = req.body;

  switch (event) {
    case "repo:push":
      // payload.push.changes[0].new.name = branch name
      // payload.push.changes[0].commits = array of commits
      console.log(`Push to ${payload.push.changes[0].new.name}`);
      break;
    case "pullrequest:fulfilled":
      // PR merged — payload.pullrequest.title, .source.branch.name, etc.
      console.log(`PR merged: ${payload.pullrequest.title}`);
      break;
  }
});

// Jira integration is automatic when both are on the same Atlassian site.
// Mentioning a Jira key (e.g., "ENG-142") in commits, branches, or PRs
// auto-links them in Jira. Smart commits allow transitions:

// git commit -m "ENG-142 #time 2h #comment Fixed the auth bug #done"
//   → Logs 2h work on ENG-142
//   → Adds comment "Fixed the auth bug"
//   → Transitions issue to Done
```

### Step 8: Code Search & Reports

```typescript
// Search code across repositories in a workspace
const searchResults = await bb("GET",
  `/workspaces/my-workspace/search/code?search_query=${encodeURIComponent(
    'lang:typescript "jwt.verify"'
  )}&pagelen=20`
);

// Get commit history with file changes
const commits = await bb("GET",
  `/repositories/my-workspace/my-repo/commits?pagelen=30`
);

// Get diff for a specific commit
const diff = await fetch(
  `${BB_BASE}/repositories/my-workspace/my-repo/diff/${commitHash}`,
  { headers: { Authorization: `Basic ${AUTH}` } }
).then(r => r.text());

// Compare two branches (useful for release notes)
const compare = await bb("GET",
  `/repositories/my-workspace/my-repo/commits?include=main&exclude=release/2.0`
);
```
