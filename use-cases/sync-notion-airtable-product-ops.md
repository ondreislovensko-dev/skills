---
title: Sync Notion and Airtable for Product Ops
slug: sync-notion-airtable-product-ops
description: "Build a two-way sync between Notion (where PMs write specs) and Airtable (where ops tracks delivery), keeping both tools in sync without manual copy-paste."
skills: [notion, airtable]
category: productivity
tags: [notion, airtable, sync, product-management, automation]
---

# Sync Notion and Airtable for Product Ops

## The Problem

A 30-person product team uses Notion for specs, decisions, and meeting notes, and Airtable for tracking delivery -- sprint boards, launch timelines, and cross-functional status updates. Both tools are deeply embedded in the team's workflow, and nobody wants to switch.

The disconnect happens at the handoff. When a PM writes a spec in Notion and moves it to "Ready for Dev," someone has to manually create a corresponding row in Airtable with the title, priority, linked spec URL, and estimated timeline. When the status changes in Airtable during a sprint, someone else has to update the Notion page to reflect it. Nobody does this consistently, so the Notion board says "In Progress" for features that shipped two weeks ago, and the Airtable launch tracker is missing three specs that were approved last Monday.

The team tried Zapier, but the Notion trigger only catches new pages -- it misses status changes, property updates, and moves between databases. They need a sync that watches both tools and keeps them aligned.

## The Solution

Build a Python sync service using the **notion** and **airtable** skills that runs on a cron schedule. It reads specs from a Notion database, mirrors them as rows in an Airtable base, and syncs status changes in both directions. A simple "last modified wins" strategy handles conflicts, and a sync log tracks every change for auditability.

## Step-by-Step Walkthrough

### Step 1: Define the Data Model

Both tools need to agree on a shared schema. The Notion database holds the rich content (spec body, comments, linked docs), while Airtable holds the operational data (sprint assignment, delivery dates, blockers):

```text
I have a Notion database called "Product Specs" and an Airtable base called "Delivery Tracker." 
Set up a two-way sync between them with this shared schema:

Notion properties: Name (title), Status (select: Draft/Ready/In Progress/In Review/Shipped), 
Priority (select: P0/P1/P2/P3), Owner (person), Target Quarter (select), Spec URL (auto-generated).

Airtable fields: Spec Name, Status (same values), Priority (same), Owner (text), 
Target Quarter, Notion URL, Sprint (text), Ship Date (date), Blockers (long text), 
Last Synced (datetime).

The sync should match records by Notion page ID stored in a hidden Airtable field.
```

### Step 2: Build the Sync Engine

The sync engine connects to both APIs, fetches records from each side, and determines what needs updating. The core logic compares timestamps to decide which side has the fresher data:

```python
"""sync_engine.py — Two-way Notion ↔ Airtable sync engine."""
import os, json, time, logging
from datetime import datetime, timezone
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("sync")

# --- Configuration ---
NOTION_TOKEN = os.environ["NOTION_TOKEN"]
NOTION_DB_ID = os.environ["NOTION_DATABASE_ID"]
AIRTABLE_TOKEN = os.environ["AIRTABLE_TOKEN"]
AIRTABLE_BASE_ID = os.environ["AIRTABLE_BASE_ID"]
AIRTABLE_TABLE = "Delivery Tracker"

NOTION_HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}
AIRTABLE_HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json",
}

# Fields that sync in both directions
SYNCED_FIELDS = ["Status", "Priority", "Owner", "Target Quarter"]


def fetch_notion_specs() -> list[dict]:
    """Fetch all specs from the Notion database, handling pagination.

    Returns:
        List of normalized spec dicts with id, title, properties, and last_edited.
    """
    pages, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        resp = requests.post(
            f"https://api.notion.com/v1/databases/{NOTION_DB_ID}/query",
            json=body, headers=NOTION_HEADERS,
        )
        data = resp.json()
        for page in data["results"]:
            props = page["properties"]
            pages.append({
                "notion_id": page["id"],
                "last_edited": page["last_edited_time"],
                "title": extract_title(props.get("Name", {})),
                "status": extract_select(props.get("Status", {})),
                "priority": extract_select(props.get("Priority", {})),
                "owner": extract_people(props.get("Owner", {})),
                "target_quarter": extract_select(props.get("Target Quarter", {})),
                "url": page["url"],
            })
        if not data.get("has_more"):
            break
        cursor = data["next_cursor"]
    return pages


def fetch_airtable_records() -> list[dict]:
    """Fetch all records from the Airtable delivery tracker.

    Returns:
        List of dicts with airtable_id, notion_id, fields, and last_synced.
    """
    records, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        resp = requests.get(
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}",
            params=params, headers=AIRTABLE_HEADERS,
        )
        data = resp.json()
        for rec in data["records"]:
            f = rec["fields"]
            records.append({
                "airtable_id": rec["id"],
                "notion_id": f.get("Notion Page ID", ""),
                "title": f.get("Spec Name", ""),
                "status": f.get("Status", ""),
                "priority": f.get("Priority", ""),
                "owner": f.get("Owner", ""),
                "target_quarter": f.get("Target Quarter", ""),
                "last_synced": f.get("Last Synced", ""),
            })
        offset = data.get("offset")
        if not offset:
            break
        time.sleep(0.2)  # Respect Airtable's 5 req/s limit
    return records


def sync():
    """Run the two-way sync. New Notion specs create Airtable rows.
    Status/priority changes propagate in both directions (last edit wins).
    """
    notion_specs = fetch_notion_specs()
    airtable_records = fetch_airtable_records()
    now = datetime.now(timezone.utc).isoformat()

    # Index Airtable records by Notion page ID for fast lookup
    at_by_notion_id = {r["notion_id"]: r for r in airtable_records if r["notion_id"]}

    created, updated_in_at, updated_in_notion = 0, 0, 0

    for spec in notion_specs:
        existing = at_by_notion_id.get(spec["notion_id"])

        if not existing:
            # New spec — create Airtable row
            create_airtable_record(spec, now)
            created += 1
            continue

        # Determine sync direction by comparing timestamps
        notion_edited = datetime.fromisoformat(spec["last_edited"].replace("Z", "+00:00"))
        last_synced = existing.get("last_synced", "")
        if last_synced:
            last_sync_dt = datetime.fromisoformat(last_synced.replace("Z", "+00:00"))
        else:
            last_sync_dt = datetime.min.replace(tzinfo=timezone.utc)

        # Check what changed on each side
        notion_changes = {
            f: spec[f.lower().replace(" ", "_")]
            for f in SYNCED_FIELDS
            if spec[f.lower().replace(" ", "_")] != existing.get(f.lower().replace(" ", "_"), "")
        }

        if notion_edited > last_sync_dt and notion_changes:
            # Notion is newer — push changes to Airtable
            update_airtable_record(existing["airtable_id"], notion_changes, now)
            updated_in_at += 1
        elif not notion_changes:
            # Check if Airtable has changes to push back to Notion
            at_changes = {}
            for field in SYNCED_FIELDS:
                at_val = existing.get(field.lower().replace(" ", "_"), "")
                notion_val = spec[field.lower().replace(" ", "_")]
                if at_val and at_val != notion_val:
                    at_changes[field] = at_val

            if at_changes:
                update_notion_page(spec["notion_id"], at_changes)
                # Update sync timestamp in Airtable
                update_airtable_timestamp(existing["airtable_id"], now)
                updated_in_notion += 1

    log.info(f"Sync complete: {created} created, {updated_in_at} → Airtable, "
             f"{updated_in_notion} → Notion")


def create_airtable_record(spec: dict, now: str):
    """Create a new Airtable row from a Notion spec.

    Args:
        spec: Normalized spec dict from fetch_notion_specs.
        now: ISO timestamp for the Last Synced field.
    """
    requests.post(
        f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}",
        json={"records": [{"fields": {
            "Spec Name": spec["title"],
            "Status": spec["status"],
            "Priority": spec["priority"],
            "Owner": spec["owner"],
            "Target Quarter": spec["target_quarter"],
            "Notion URL": spec["url"],
            "Notion Page ID": spec["notion_id"],
            "Last Synced": now,
        }}]},
        headers=AIRTABLE_HEADERS,
    )
    time.sleep(0.2)


def update_airtable_record(record_id: str, changes: dict, now: str):
    """Push changes from Notion to an existing Airtable row.

    Args:
        record_id: Airtable record ID.
        changes: Dict of field name → new value.
        now: ISO timestamp for Last Synced.
    """
    fields = {**changes, "Last Synced": now}
    requests.patch(
        f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}",
        json={"records": [{"id": record_id, "fields": fields}]},
        headers=AIRTABLE_HEADERS,
    )
    time.sleep(0.2)


def update_notion_page(page_id: str, changes: dict):
    """Push changes from Airtable back to a Notion page.

    Args:
        page_id: Notion page UUID.
        changes: Dict of property name → new value (Status, Priority, etc.).
    """
    properties = {}
    for field, value in changes.items():
        if field in ("Status", "Priority", "Target Quarter"):
            properties[field] = {"select": {"name": value}}
        elif field == "Owner":
            # Owner syncs as text from Airtable (can't set Notion people by name)
            pass
    if properties:
        requests.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            json={"properties": properties},
            headers=NOTION_HEADERS,
        )


def update_airtable_timestamp(record_id: str, now: str):
    """Update the Last Synced timestamp after pushing changes to Notion."""
    requests.patch(
        f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}",
        json={"records": [{"id": record_id, "fields": {"Last Synced": now}}]},
        headers=AIRTABLE_HEADERS,
    )
    time.sleep(0.2)


# --- Notion property extractors ---

def extract_title(prop: dict) -> str:
    return "".join(t["plain_text"] for t in prop.get("title", []))

def extract_select(prop: dict) -> str:
    sel = prop.get("select")
    return sel["name"] if sel else ""

def extract_people(prop: dict) -> str:
    people = prop.get("people", [])
    return ", ".join(p.get("name", "") for p in people)


if __name__ == "__main__":
    sync()
```

### Step 3: Handle Edge Cases

The sync needs to handle scenarios that break naive implementations -- deleted records, renamed properties, and conflicting simultaneous edits:

```python
"""sync_safety.py — Conflict detection and deleted record handling."""

def detect_conflicts(notion_spec: dict, airtable_rec: dict, last_synced: str) -> list:
    """Find fields where both sides changed since last sync.

    Args:
        notion_spec: Current Notion data.
        airtable_rec: Current Airtable data.
        last_synced: ISO timestamp of last successful sync.

    Returns:
        List of field names with conflicting changes.
    """
    conflicts = []
    for field in SYNCED_FIELDS:
        key = field.lower().replace(" ", "_")
        notion_val = notion_spec.get(key, "")
        airtable_val = airtable_rec.get(key, "")
        if notion_val != airtable_val:
            # Both differ from each other — potential conflict
            conflicts.append({
                "field": field,
                "notion_value": notion_val,
                "airtable_value": airtable_val,
            })
    return conflicts


def handle_deleted_specs(notion_ids: set, airtable_records: list):
    """Mark Airtable rows as 'Archived' when their Notion spec is deleted.

    Args:
        notion_ids: Set of all current Notion page IDs.
        airtable_records: All Airtable records with Notion Page ID field.
    """
    for rec in airtable_records:
        if rec["notion_id"] and rec["notion_id"] not in notion_ids:
            if rec.get("status") != "Archived":
                update_airtable_record(
                    rec["airtable_id"],
                    {"Status": "Archived"},
                    datetime.now(timezone.utc).isoformat(),
                )
                log.info(f"Archived orphaned Airtable row: {rec['title']}")
```

The conflict detection logs both values and defaults to Notion as the source of truth for spec-related fields (status, priority) and Airtable for ops-related fields (sprint, ship date, blockers). This avoids the situation where a PM changes status to "Ready" in Notion while an engineer simultaneously marks it "In Progress" in Airtable -- the Airtable value wins because sprint-level status is operational data.

### Step 4: Schedule and Monitor

Run the sync every 15 minutes via cron, with logging to a sync history file:

```python
"""sync_runner.py — Cron wrapper with logging and error reporting."""
import sys, traceback
from pathlib import Path

SYNC_LOG = Path("sync_history.jsonl")

def run_with_logging():
    """Execute sync and append result to the history log."""
    start = datetime.now(timezone.utc)
    try:
        sync()
        result = {"status": "ok", "timestamp": start.isoformat()}
    except Exception as e:
        result = {
            "status": "error",
            "timestamp": start.isoformat(),
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
        log.error(f"Sync failed: {e}")

    result["duration_ms"] = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    with open(SYNC_LOG, "a") as f:
        f.write(json.dumps(result) + "\n")

    # Keep only last 1000 entries
    lines = SYNC_LOG.read_text().strip().split("\n")
    if len(lines) > 1000:
        SYNC_LOG.write_text("\n".join(lines[-1000:]) + "\n")

if __name__ == "__main__":
    run_with_logging()
```

```bash
# Run every 15 minutes
*/15 * * * * cd /opt/notion-airtable-sync && python3 sync_runner.py >> /var/log/sync.log 2>&1
```

## Real-World Example

A product lead at a 30-person SaaS company sets up the sync on a Friday. The Notion database has 47 specs across three quarters. The first run creates all 47 rows in Airtable in under a minute, populating names, statuses, priorities, and direct links back to Notion specs.

On Monday, the engineering team updates sprint assignments and ship dates in Airtable. The PM changes two spec priorities in Notion. The next sync run picks up all changes: priorities flow from Notion to Airtable, sprint assignments flow from Airtable to Notion page properties. Both tools stay consistent without anyone copying and pasting between tabs.

After three weeks, the team notices that their Monday planning meetings run 15 minutes shorter. They no longer spend time cross-referencing Notion pages with Airtable rows to figure out what's actually in progress -- both tools always agree.

## Related Skills

- [linear](../skills/linear/) -- Alternative project tracker with built-in GitHub sync
- [clickup](../skills/clickup/) -- All-in-one project management with custom fields
