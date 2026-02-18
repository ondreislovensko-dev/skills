---
title: "Build a Multi-Agent System with the A2A Protocol"
slug: build-multi-agent-system-with-a2a
description: "Connect independent AI agents built on different frameworks into a collaborative system using the Agent2Agent protocol for discovery, task delegation, and orchestration."
skills: [a2a-protocol, coding-agent, mcp-server-builder]
category: development
tags: [a2a, multi-agent, agent-interoperability, orchestration, ai-agents]
---

# Build a Multi-Agent System with the A2A Protocol

## The Problem

A 40-person company has four AI agents built by different teams on different frameworks: a research agent on LangGraph, a code generation agent on Google ADK, a data analysis agent on CrewAI, and a writing agent on custom Python. Each one works well in isolation. The problem is they cannot talk to each other.

When someone needs research done, code written based on findings, and a report generated, a human has to manually copy outputs between agents. There is no way for the code agent to ask the research agent for clarification. There is no shared task tracking. There is no discovery mechanism to know what agents even exist. And every agent exposes a different API, so building an integration layer means writing four bespoke connectors that break every time an agent updates.

A quarterly business report that should take minutes takes 3 hours of manual copying, reformatting, and context-shuttling between tools.

## The Solution

Use **a2a-protocol** to make each agent A2A-compliant with standard Agent Cards and task management, **coding-agent** to implement the orchestrator that discovers and delegates to specialized agents, and **mcp-server-builder** to give individual agents tool access while they collaborate via A2A.

## Step-by-Step Walkthrough

### Step 1: Wrap Existing Agents as A2A Servers

```text
We have 4 agents on different frameworks:
1. Research agent (LangGraph) — searches web, summarizes papers
2. Code agent (Google ADK) — generates and refactors code
3. Data agent (CrewAI) — analyzes datasets, creates visualizations
4. Writer agent (custom Python) — writes reports, blog posts, docs

Wrap each one as an A2A server. Create Agent Cards that describe their
skills, supported input/output modes, and capabilities (streaming, push
notifications). Each agent should serve its card at /.well-known/agent.json
and accept standard A2A messages. Use the Python a2a-sdk.

Show me the full implementation for the research agent as an example,
and the Agent Card JSON for all four.
```

The key insight with A2A is that wrapping an existing agent does not require rewriting it. A thin adapter layer sits between the protocol and the framework. For the LangGraph research agent, a Starlette-based A2A server receives incoming messages, feeds them to the existing LangGraph chain, streams intermediate results as `TaskStatusUpdateEvent`s, and returns the final answer as a completed task.

Each agent publishes an Agent Card at `/.well-known/agent.json` describing what it can do. Here is the research agent's card:

```json
{
  "name": "Research Agent",
  "description": "Searches the web, summarizes academic papers, and gathers market intelligence",
  "url": "https://agents.internal/research",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true
  },
  "skills": [
    {
      "id": "web-research",
      "name": "Web Research",
      "description": "Search and synthesize information from multiple sources",
      "tags": ["research", "web", "summarization"],
      "examples": ["Find recent papers on transformer architectures", "Market analysis of CI/CD tools"]
    }
  ],
  "defaultInputModes": ["text/plain"],
  "defaultOutputModes": ["text/plain", "application/json"]
}
```

The other three agents follow the same pattern. The data agent advertises `application/json` and `image/png` output modes (for charts). The writer advertises `text/markdown`. These declarations let the orchestrator make smart routing decisions -- it knows which agents produce what formats before sending a single message.

### Step 2: Build the Orchestrator

```text
Create an A2A orchestrator that:
1. Discovers all available agents by fetching their Agent Cards from a
   registry (a JSON file listing agent URLs for now)
2. Receives user requests and plans which agents to involve
3. Supports sequential chains (research → write) and parallel fan-out
   (ask research + data simultaneously)
4. Passes context between agents — the output of one becomes input to next
5. Handles the input-required state (agent needs clarification from user)
6. Tracks all tasks with status, shows progress to the user
7. Is itself an A2A server (so it can be composed into larger systems)

The orchestrator should use an LLM to decide the execution plan based on
the user's request and the available agent skills.
```

The orchestrator is itself an A2A server with one skill: "plan-and-execute." On startup, it fetches Agent Cards from every URL in the registry and builds an in-memory capability index. When a user request arrives, an LLM receives the request along with all available agent skills and generates an execution plan:

```python
# Simplified execution plan for "Write a quarterly report with revenue charts"
plan = {
    "steps": [
        {"agent": "research", "input": "Q1 2026 revenue trends and market analysis", "parallel_group": 1},
        {"agent": "data", "input": "Generate revenue charts from sales_data.csv", "parallel_group": 1},
        {"agent": "writer", "input": "Compile quarterly report using {research.output} and {data.output}", "depends_on": [1]}
    ]
}
```

Steps in the same `parallel_group` execute concurrently. Steps with `depends_on` wait for their dependencies to complete and receive the outputs as context. The orchestrator sends standard A2A messages to each agent, handles streaming responses, and aggregates results.

### Step 3: Enable Direct Agent-to-Agent Delegation

```text
Add the ability for agents to delegate to each other directly (not just
through the orchestrator). For example: the writer agent needs data to
include in a report, so it sends an A2A message to the data agent asking
for a chart. The data agent returns an artifact (PNG image) that the
writer includes in the report.

Implement this for a concrete scenario: user asks the writer to create
a quarterly report. The writer delegates to data agent for charts and
research agent for market insights, then assembles everything into a
cohesive report.
```

This is where multi-agent systems get interesting. The writer agent now includes A2A client capabilities -- it can discover other agents and send them requests mid-task. When writing a quarterly report, the writer:

1. Discovers the data agent via its Agent Card
2. Sends a structured request for specific charts with JSON parameters
3. Receives artifacts back (PNG images and data tables)
4. Discovers the research agent and requests market insights
5. Assembles everything into the final report

The user sees streaming status updates throughout: "Writing report... Requesting sales data from data agent... Generating chart... Incorporating results..." The entire delegation chain is tracked through A2A task IDs, so every step is auditable.

### Step 4: Add Push Notifications for Long-Running Tasks

```text
The data analysis agent can take 5-10 minutes for complex queries. Set up
push notifications so:
1. Client sends a task to the orchestrator
2. Orchestrator delegates to data agent with a webhook URL
3. Data agent processes async, POSTs status updates to webhook
4. Orchestrator receives updates and forwards to the original client
5. Support reconnection — if the client disconnects, they can poll for
   the task status later using the task ID

Also implement a simple task dashboard that shows all active tasks across
all agents with their current status.
```

Without push notifications, every client has to hold a connection open for the entire duration of a task. For a 10-minute data analysis job, that is wasteful and fragile.

The push notification flow uses webhooks: the orchestrator includes a callback URL in its outbound A2A requests, the data agent POSTs status updates to that webhook as it progresses, and the orchestrator forwards updates to the original client. A SQLite-backed task store persists state across reconnections -- if a client disconnects and comes back, it can poll the task by ID and pick up where it left off.

A lightweight web dashboard polls the orchestrator's `ListTasks` endpoint and displays all active tasks with their status, duration, and which agents are involved.

### Step 5: Secure and Harden for Production

```text
Secure the multi-agent system:
1. Agent-to-agent authentication: each agent has a service account token,
   declared in its Agent Card's authentication section
2. TLS on all A2A endpoints
3. Rate limiting per client
4. Input validation: reject messages with unsupported content types
5. Task timeout: auto-cancel tasks that run longer than 30 minutes
6. Audit logging: log all inter-agent communications with task IDs
7. Health checks: /health endpoint on each agent, orchestrator monitors

Also add OpenTelemetry tracing so we can see the full request flow
across all agents in Jaeger.
```

Production means trust boundaries. Every A2A server gets bearer token authentication, TLS via cert-manager, and middleware for rate limiting and input validation. A task reaper runs every minute and cancels anything older than 30 minutes. Structured logging with correlation IDs ties every message to its originating task.

The most valuable addition is OpenTelemetry tracing using the a2a-sdk's telemetry integration. A single user request fans out across four agents -- without distributed tracing, debugging a slow report is guesswork. With it, you open Jaeger and see exactly which agent took how long, where retries happened, and where the bottleneck lives.

## Real-World Example

The AI platform team wraps each of their four agents in under a day per agent -- no rewrites, just thin A2A adapters. The orchestrator connects all four, and users start describing what they need in natural language instead of manually routing between tools.

Direct agent-to-agent delegation enables the writer to pull charts from the data agent and insights from the research agent without human intervention. A quarterly report that previously took 3 hours of manual coordination now completes in 8 minutes end-to-end.

OpenTelemetry tracing reveals that 70% of total time is spent in the data agent's SQL queries. The team optimizes those queries and cuts report generation to 3 minutes. The system is also composable -- when a fifth agent (a compliance reviewer) joins the company later, it publishes an Agent Card and the orchestrator discovers it automatically. No code changes needed.
