---
title: "Build a Realtime Collaborative Editor"
slug: build-realtime-collaborative-editor
description: "Create a collaborative text editor where multiple users can edit documents simultaneously with live cursors, presence indicators, and conflict-free synchronization."
skills: [websocket-builder, realtime-database, auth-system-setup]
category: development
tags: [websocket, collaboration, realtime, editor, crdt, presence]
---

# Build a Realtime Collaborative Editor

## The Problem

Noa is building an internal knowledge base tool for her five-person engineering team. The key requirement: multiple people need to edit the same document at the same time, like Google Docs but self-hosted and private. Off-the-shelf solutions either cost $12/user/month (adds up fast as the company grows) or run on someone else's servers -- which fails the data residency requirements for their enterprise clients.

The real engineering challenge is conflict resolution. When two people type at the same position simultaneously, both edits need to survive. Naive approaches (last-write-wins, locking) either lose data or destroy the collaborative experience. Noa needs live cursors showing who is editing where, real-time text synchronization without conflicts, and user authentication so edits are attributed.

## The Solution

Use **auth-system-setup** to handle user accounts and session management, **websocket-builder** to create the real-time communication layer between clients and server, and **realtime-database** to persist document state and sync changes across connected clients with conflict resolution.

## Step-by-Step Walkthrough

### Step 1: Set Up Authentication and Document Permissions

```text
I need user authentication for the editor. Simple email + password login,
JWT sessions, and document-level permissions: owner, editor, viewer.
The owner can share documents with others and set their role. Use
PostgreSQL for storage.
```

Authentication is straightforward: email/password registration with bcrypt, JWT sessions with 24-hour expiry. Each user gets a randomly assigned avatar color from 12 distinct options -- these colors identify cursors in the editor later.

Document access uses a simple permission model:

| Role | Read | Write | Share | Delete |
|---|---|---|---|---|
| Owner | Yes | Yes | Yes | Yes |
| Editor | Yes | Yes | No | No |
| Viewer | Yes | No | No | No |

```typescript
// auth/permissions.ts — Document access control

// POST /documents/:id/share — owner only
// Body: { email: string, role: 'editor' | 'viewer' }
// Looks up user by email, creates permission record

// Middleware: requireDocumentAccess(minRole)
// Checks JWT → extracts user → queries document_permissions
// Returns 403 if role is insufficient
```

Document creation automatically assigns the creator as owner. The share endpoint lets owners invite collaborators by email and assign roles.

### Step 2: Build the WebSocket Server for Real-Time Communication

```text
Set up the WebSocket server. Each document is a "room" — when a user
opens a document, they join that room. I need: connection authentication
(verify JWT on connect), room management, and message routing so edits
in one client reach all others in the same room instantly.
```

Every document is a WebSocket room. When a user opens a document, the connection flow is:

1. Client connects: `ws://host/ws?token=JWT&docId=abc123`
2. Server verifies JWT (same key as HTTP auth)
3. Server checks `document_permissions` for this user and document
4. If authorized: join the room, broadcast a presence update to other editors
5. If not: close connection with a 4403 code

The room manager tracks connections per document:

```typescript
// ws/rooms.ts — Room management

// Map<documentId, Set<Connection>>
// Connection: { ws, userId, displayName, avatarColor, role, cursor }

rooms.join(docId, connection);     // add to room, broadcast "user_joined"
rooms.leave(docId, userId);        // remove from room, broadcast "user_left"
rooms.broadcast(docId, message);   // send to all in room (optionally excluding sender)
```

Messages flow in both directions. Clients send operations (text changes), cursor positions, and selection ranges. The server relays operations to all other room members, sends presence updates, and provides a full document sync on initial connect.

A 30-second heartbeat catches disconnected clients. If a client misses 2 consecutive pongs, the server drops the connection and broadcasts a leave event.

### Step 3: Implement Conflict-Free Document Synchronization

```text
The hard part: when two people type at the same position simultaneously,
the edits need to merge without losing either person's changes. Implement
operational transformation or CRDTs — whichever is simpler for a text
editor. Persist every operation so we have full history.
```

This is the hard part. Two approaches exist: Operational Transformation (OT) and CRDTs. OT requires a central transform server and gets complex fast. CRDTs (Conflict-free Replicated Data Types) are simpler -- merges are commutative, so the order operations arrive does not matter.

The editor uses Yjs, a battle-tested CRDT library used by Notion, Jupyter, and others:

```typescript
// sync/crdt.ts — Yjs integration

import * as Y from 'yjs';

// One Y.Doc per document
const doc = new Y.Doc();
const yText = doc.getText('content');     // shared text, supports concurrent edits
const yMeta = doc.getMap('metadata');     // title, last_modified, etc.
```

When two users type at the same position simultaneously -- say User A types "hello" and User B types "world" at position 0 -- the CRDT merges them deterministically by user ID order. No data lost, no manual conflict resolution needed.

The server-side persistence layer:

- **On client connect**: send the Y.Doc state as a sync step
- **On client update**: apply to server Y.Doc, broadcast to room
- **Periodic persistence**: debounced save to PostgreSQL every 2 seconds
- **Full state save**: on last client disconnect

```sql
-- Document storage
CREATE TABLE documents (
  id UUID PRIMARY KEY,
  title TEXT,
  yjs_state BYTEA,           -- compressed binary snapshot of Y.Doc
  version INTEGER DEFAULT 0,
  updated_at TIMESTAMPTZ
);

CREATE TABLE document_updates (
  id BIGSERIAL PRIMARY KEY,
  document_id UUID REFERENCES documents(id),
  update_data BYTEA,          -- individual Y.Doc update
  user_id UUID,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

The `document_updates` table is an append-only log. Full edit history can be replayed by applying updates in order -- useful for "who changed this paragraph?" questions.

A major bonus: Yjs works offline. A client can edit while disconnected, and changes merge cleanly on reconnect. No special handling needed.

### Step 4: Add Live Cursors and Presence Indicators

```text
Show each user's cursor position and selection in real time. Each user
gets a unique color. Show a small name label next to each remote cursor.
Also show a presence list in the sidebar — who's currently viewing the
document and whether they're actively editing or idle.
```

Live cursors make collaboration feel real. Each remote user's cursor is a 2px colored bar with a floating name label, rendered as CodeMirror 6 decorations:

- **Cursor**: vertical bar in the user's avatar color
- **Name label**: small floating div above the cursor with the user's name
- **Selection**: semi-transparent highlight at 20% opacity
- **Idle state**: cursors fade to 50% opacity after 5 seconds of no movement

Cursor updates are throttled to 50ms intervals (20 updates/second). Selection changes send immediately. This keeps the experience smooth without overwhelming the WebSocket.

The sidebar presence panel shows everyone currently in the document:

- **Green dot**: actively editing
- **Yellow dot**: idle for 30+ seconds
- **Grey dot**: viewer (read-only access)
- **Location hint**: "Editing near line 42"

A 5-second grace period on disconnect prevents the presence list from flickering during page refreshes -- the user disappears from the list only if they do not reconnect within 5 seconds.

### Step 5: Build the Editor UI with Document Management

```text
Create the frontend: a clean editor interface with a document list sidebar,
the collaborative editor in the center, and the presence panel on the right.
Use CodeMirror 6 for the editor. Add markdown support since our team writes
docs in markdown.
```

The frontend uses React with CodeMirror 6 as the editor engine. The layout is a three-column CSS Grid:

- **Left sidebar (240px)**: document list with search and "New Document" button
- **Center (flex)**: CodeMirror editor, full height
- **Right panel (200px)**: presence list and share button

CodeMirror 6 extensions handle the heavy lifting:

```typescript
// editor/codemirror-setup.ts

const extensions = [
  markdown(),                         // syntax highlighting + preview
  yCollab(yText, provider),          // Yjs collaboration binding
  remoteCursors(),                   // renders other users' cursors
  keymap.of([...defaultKeymap, ...markdownKeymap]),
  customTheme,                       // clean typography, light theme
];
```

The connection status bar at the bottom shows the current state: "Connected -- 3 collaborators" (green dot), "Reconnecting..." (yellow dot, auto-retry), or "Offline -- changes will sync when reconnected" (red dot). Yjs handles the offline case transparently -- edits queue locally and merge on reconnect.

## Real-World Example

Noa's five-person team sets up the self-hosted editor on a small VPS in a weekend. They start writing specs, runbooks, and design docs collaboratively. Live cursors make pair-writing unexpectedly fun -- two engineers can hammer out an API spec in real time, seeing each other's changes as they type.

The CRDT earns its keep during an incident. Two engineers edit the same runbook simultaneously while troubleshooting a production issue -- one updating the timeline while the other documents the root cause. Their edits merge seamlessly with no conflicts and no coordination overhead.

The full edit history also proves useful. When a question arises about when a particular decision was documented in a design spec, the team replays the document history to the exact update. Total cost: one $5/month VPS instead of $60/month for a hosted collaboration tool.
