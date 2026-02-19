---
name: notion
category: productivity
version: 1.0.0
description: >-
  Build integrations with the Notion API — databases, pages, blocks, comments,
  search, and OAuth. Use when tasks involve reading or writing Notion workspace
  data, syncing external tools with Notion databases, building dashboards from
  Notion content, or automating page creation and updates.
author: terminal-skills
tags: [notion, api, productivity, databases, workspace, automation]
---

# Notion API Integration

Build automations and integrations with Notion workspaces using the official REST API.

## Authentication

### Internal Integration (own workspace)

Create an integration at https://www.notion.so/my-integrations, copy the token, and share target pages/databases with the integration.

```bash
export NOTION_TOKEN="ntn_..."
```

### Public Integration (OAuth)

For multi-user apps, implement the OAuth flow:

```python
"""notion_oauth.py — OAuth 2.0 flow for public Notion integrations."""

AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
TOKEN_URL = "https://api.notion.com/v1/oauth/token"

def get_auth_url(client_id: str, redirect_uri: str) -> str:
    """Build the OAuth authorization URL.

    Args:
        client_id: From your Notion integration settings.
        redirect_uri: Where Notion redirects after authorization.
    """
    return (
        f"{AUTHORIZE_URL}?client_id={client_id}"
        f"&response_type=code&owner=user"
        f"&redirect_uri={redirect_uri}"
    )

def exchange_code(code: str, client_id: str, client_secret: str) -> dict:
    """Exchange authorization code for access token.

    Args:
        code: The code from Notion's redirect.
        client_id: Integration client ID.
        client_secret: Integration client secret.
    """
    import requests, base64
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(TOKEN_URL, json={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": "https://yourapp.com/callback",
    }, headers={
        "Authorization": f"Basic {credentials}",
        "Notion-Version": "2022-06-28",
    })
    return resp.json()  # Contains access_token, workspace_id, bot_id
```

## Core API Patterns

All requests use `Notion-Version: 2022-06-28` header and Bearer token auth.

### Database Operations

```python
"""notion_db.py — Query, create, and update Notion databases."""
import requests

API = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": "Bearer ntn_...",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

def query_database(database_id: str, filter_obj: dict = None, sorts: list = None) -> list:
    """Query a Notion database with optional filters and sorting.

    Args:
        database_id: UUID of the database (from URL or API).
        filter_obj: Notion filter object for narrowing results.
        sorts: List of sort objects (property + direction).

    Returns:
        List of page objects matching the query.
    """
    body = {}
    if filter_obj:
        body["filter"] = filter_obj
    if sorts:
        body["sorts"] = sorts

    pages = []
    has_more = True
    start_cursor = None

    while has_more:
        if start_cursor:
            body["start_cursor"] = start_cursor
        resp = requests.post(f"{API}/databases/{database_id}/query",
                             json=body, headers=HEADERS)
        data = resp.json()
        pages.extend(data["results"])
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return pages

def create_page(database_id: str, properties: dict, children: list = None) -> dict:
    """Create a new page (row) in a Notion database.

    Args:
        database_id: Target database UUID.
        properties: Property values matching database schema.
        children: Optional list of block objects for page content.
    """
    body = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }
    if children:
        body["children"] = children
    resp = requests.post(f"{API}/pages", json=body, headers=HEADERS)
    return resp.json()

def update_page(page_id: str, properties: dict) -> dict:
    """Update properties of an existing page.

    Args:
        page_id: UUID of the page to update.
        properties: Property values to change.
    """
    resp = requests.patch(f"{API}/pages/{page_id}",
                          json={"properties": properties}, headers=HEADERS)
    return resp.json()
```

### Property Types

Common property value formats for `create_page` and `update_page`:

```python
# Property value examples for database pages
properties = {
    # Title (required — every database has one title property)
    "Name": {"title": [{"text": {"content": "New task"}}]},

    # Rich text
    "Description": {"rich_text": [{"text": {"content": "Details here"}}]},

    # Select (single choice)
    "Status": {"select": {"name": "In Progress"}},

    # Multi-select
    "Tags": {"multi_select": [{"name": "frontend"}, {"name": "urgent"}]},

    # Number
    "Story Points": {"number": 5},

    # Date (with optional end for ranges)
    "Due Date": {"date": {"start": "2025-03-15", "end": "2025-03-20"}},

    # Checkbox
    "Done": {"checkbox": True},

    # URL
    "Link": {"url": "https://example.com"},

    # Email
    "Contact": {"email": "team@example.com"},

    # People (assign users by their Notion user ID)
    "Assignee": {"people": [{"id": "user-uuid-here"}]},

    # Relation (link to pages in another database)
    "Project": {"relation": [{"id": "related-page-uuid"}]},
}
```

### Block Operations

Pages are made of blocks. Append, read, or delete blocks to build page content:

```python
def append_blocks(page_id: str, blocks: list) -> dict:
    """Append content blocks to a page.

    Args:
        page_id: UUID of the page.
        blocks: List of block objects to append.
    """
    resp = requests.patch(f"{API}/blocks/{page_id}/children",
                          json={"children": blocks}, headers=HEADERS)
    return resp.json()

# Block examples
blocks = [
    # Heading
    {"type": "heading_2", "heading_2": {
        "rich_text": [{"text": {"content": "Sprint Summary"}}]
    }},
    # Paragraph
    {"type": "paragraph", "paragraph": {
        "rich_text": [{"text": {"content": "This sprint focused on..."}}]
    }},
    # Bulleted list
    {"type": "bulleted_list_item", "bulleted_list_item": {
        "rich_text": [{"text": {"content": "Shipped auth module"}}]
    }},
    # To-do
    {"type": "to_do", "to_do": {
        "rich_text": [{"text": {"content": "Write tests"}}],
        "checked": False,
    }},
    # Code block
    {"type": "code", "code": {
        "rich_text": [{"text": {"content": "console.log('hello')"}}],
        "language": "javascript",
    }},
    # Callout
    {"type": "callout", "callout": {
        "rich_text": [{"text": {"content": "Important note"}}],
        "icon": {"emoji": "⚠️"},
    }},
    # Table (2 columns, 1 row)
    {"type": "table", "table": {
        "table_width": 2, "has_column_header": True,
        "children": [
            {"type": "table_row", "table_row": {"cells": [
                [{"text": {"content": "Metric"}}],
                [{"text": {"content": "Value"}}],
            ]}},
            {"type": "table_row", "table_row": {"cells": [
                [{"text": {"content": "Uptime"}}],
                [{"text": {"content": "99.9%"}}],
            ]}},
        ],
    }},
]
```

### Search

```python
def search_workspace(query: str, object_type: str = None) -> list:
    """Search across all pages and databases in the workspace.

    Args:
        query: Search text.
        object_type: Optional filter — "page" or "database".
    """
    body = {"query": query}
    if object_type:
        body["filter"] = {"value": object_type, "property": "object"}
    resp = requests.post(f"{API}/search", json=body, headers=HEADERS)
    return resp.json()["results"]
```

## Pagination

All list endpoints return max 100 items. Always paginate:

```python
def get_all_blocks(block_id: str) -> list:
    """Retrieve all child blocks, handling pagination.

    Args:
        block_id: UUID of the parent block or page.
    """
    blocks, cursor = [], None
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        resp = requests.get(f"{API}/blocks/{block_id}/children",
                            params=params, headers=HEADERS)
        data = resp.json()
        blocks.extend(data["results"])
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return blocks
```

## Rate Limits

- **3 requests per second** per integration
- Implement exponential backoff on 429 responses
- Batch operations where possible (append multiple blocks in one call)

```python
import time

def safe_request(method, url, **kwargs):
    """Make a rate-limit-aware request with retry."""
    for attempt in range(5):
        resp = requests.request(method, url, headers=HEADERS, **kwargs)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 2 ** attempt))
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise Exception("Rate limit exceeded after 5 retries")
```

## Common Patterns

### Sync External Data into Notion

```python
def sync_github_issues(database_id: str, issues: list[dict]):
    """Sync GitHub issues into a Notion database, updating existing or creating new.

    Args:
        database_id: Target Notion database.
        issues: List of dicts with keys: number, title, state, labels, url.
    """
    # Get existing pages to avoid duplicates
    existing = query_database(database_id)
    existing_numbers = {}
    for page in existing:
        num_prop = page["properties"].get("Issue #", {})
        if num_prop.get("number"):
            existing_numbers[int(num_prop["number"])] = page["id"]

    for issue in issues:
        props = {
            "Name": {"title": [{"text": {"content": issue["title"]}}]},
            "Issue #": {"number": issue["number"]},
            "Status": {"select": {"name": "Open" if issue["state"] == "open" else "Closed"}},
            "Labels": {"multi_select": [{"name": l} for l in issue["labels"]]},
            "URL": {"url": issue["url"]},
        }
        if issue["number"] in existing_numbers:
            update_page(existing_numbers[issue["number"]], props)
        else:
            create_page(database_id, props)
```

### Export Notion Database to CSV

```python
import csv

def export_to_csv(database_id: str, output_path: str):
    """Export all rows from a Notion database to CSV.

    Args:
        database_id: Source database UUID.
        output_path: Path for the output CSV file.
    """
    pages = query_database(database_id)
    if not pages:
        return

    # Extract property names from first page
    prop_names = list(pages[0]["properties"].keys())

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=prop_names)
        writer.writeheader()
        for page in pages:
            row = {}
            for name in prop_names:
                prop = page["properties"][name]
                # Extract plain text value based on property type
                ptype = prop["type"]
                if ptype == "title":
                    row[name] = "".join(t["plain_text"] for t in prop["title"])
                elif ptype == "rich_text":
                    row[name] = "".join(t["plain_text"] for t in prop["rich_text"])
                elif ptype == "number":
                    row[name] = prop["number"]
                elif ptype == "select":
                    row[name] = prop["select"]["name"] if prop["select"] else ""
                elif ptype == "multi_select":
                    row[name] = ", ".join(s["name"] for s in prop["multi_select"])
                elif ptype == "date":
                    row[name] = prop["date"]["start"] if prop["date"] else ""
                elif ptype == "checkbox":
                    row[name] = prop["checkbox"]
                else:
                    row[name] = str(prop.get(ptype, ""))
            writer.writerow(row)
```

## Guidelines

- Always share pages/databases with your integration before accessing them
- Use database queries with filters instead of fetching all pages and filtering client-side
- Notion API returns rich text as arrays of text objects -- always join them for plain text
- Block children can be nested (toggle lists, columns) -- recurse when reading full pages
- The API does not support creating databases with all property types -- some (like rollup, formula) must be configured in the Notion UI
- Archive pages instead of deleting them (`update_page(id, {"archived": True})`)
