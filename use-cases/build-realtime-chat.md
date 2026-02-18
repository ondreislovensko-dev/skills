---
title: "Build a Real-Time Chat Feature for a Web Application"
slug: build-realtime-chat
description: "Implement a production-ready real-time messaging system with WebSockets, message persistence, and online presence."
skills: [websocket-builder, realtime-database]
category: development
tags: [websocket, chat, real-time, messaging, backend]
---

# Build a Real-Time Chat Feature for a Web Application

## The Problem

Adding real-time chat to an existing application seems straightforward -- open a WebSocket, send messages. Tutorials make it look like a weekend project. But production chat is the other 80%: connection management with automatic reconnection, message ordering guarantees when two people type at the same time, deduplication when a flaky connection retries a send, read receipts, typing indicators, online presence tracking, and message persistence with efficient pagination for channels with 50,000 messages.

Most teams either ship a fragile implementation that drops messages during reconnection, or they spend weeks building infrastructure that a dedicated messaging product already handles. The middle ground -- a solid, production-grade chat system that fits into an existing app -- is surprisingly hard to find examples of.

## The Solution

Use the **websocket-builder** skill to set up the WebSocket server with room management, connection lifecycle, and event routing, then use **realtime-database** to handle message persistence, efficient retrieval, and sync.

## Step-by-Step Walkthrough

### Step 1: Set Up the WebSocket Server with Rooms

```text
I have a Node.js/Express app with PostgreSQL. I need to add real-time chat.
Users can have direct messages and group channels (up to 50 members).
Set up the WebSocket server with room management and authentication.
```

The WebSocket layer handles authentication on connection, room management, and message routing. Every connection starts with a JWT handshake -- no anonymous connections, ever.

```typescript
// ws/server.ts — WebSocket server with auth handshake

import { WebSocketServer } from 'ws';
import { verifyJWT } from '../auth/jwt';
import { RoomManager } from './rooms';

const wss = new WebSocketServer({ noServer: true });
const rooms = new RoomManager();

// Upgrade HTTP → WebSocket only after JWT validation
server.on('upgrade', async (req, socket, head) => {
  const token = new URL(req.url!, `http://${req.headers.host}`).searchParams.get('token');
  const user = await verifyJWT(token);
  if (!user) { socket.destroy(); return; }

  wss.handleUpgrade(req, socket, head, (ws) => {
    ws.userId = user.id;
    ws.displayName = user.name;

    // Auto-join all channels the user belongs to
    const channels = await getUserChannels(user.id);
    channels.forEach(ch => rooms.join(ch.id, ws));

    // Heartbeat: ping every 30s, mark offline after 90s of no pong
    ws.isAlive = true;
    ws.on('pong', () => { ws.isAlive = true; });
  });
});
```

Messages flow: client sends to server, server persists to database, server broadcasts to room. The persistence step happens before the broadcast -- if the server crashes between persist and broadcast, reconnecting clients catch up via history sync. No messages are lost.

### Step 2: Design the Message Storage Schema

```text
Design the database schema for chat. I need: channels (direct + group),
messages with text and attachments, read receipts per user, and efficient
pagination for loading message history (latest messages first).
```

The schema avoids a common trap: per-message read receipts. Tracking "user X read message Y" for every message in every channel creates a table that grows quadratically. Instead, each channel membership stores a `last_read_at` timestamp. Unread count becomes a simple query: messages where `created_at > last_read_at`.

```sql
-- migrations/002_chat_schema.sql

CREATE TABLE channels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type TEXT NOT NULL CHECK (type IN ('direct', 'group')),
  name TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE channel_members (
  channel_id UUID REFERENCES channels(id) ON DELETE CASCADE,
  user_id UUID REFERENCES users(id),
  role TEXT DEFAULT 'member',
  joined_at TIMESTAMPTZ DEFAULT now(),
  last_read_at TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (channel_id, user_id)
);

CREATE TABLE messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_id UUID REFERENCES channels(id) ON DELETE CASCADE,
  sender_id UUID REFERENCES users(id),
  content TEXT NOT NULL,
  type TEXT DEFAULT 'text',
  reply_to_id UUID REFERENCES messages(id),
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ
);

-- History pagination: newest messages first, efficiently
CREATE INDEX idx_messages_history ON messages (channel_id, created_at DESC);

-- User's channels lookup
CREATE INDEX idx_member_channels ON channel_members (user_id, channel_id);

-- Active messages only (skip soft-deleted)
CREATE INDEX idx_messages_active ON messages (channel_id, id)
  WHERE deleted_at IS NULL;
```

This schema scales to millions of messages without a separate receipts table. The `last_read_at` approach means unread counts are fast even for channels with years of history.

### Step 3: Implement Message Delivery with Ordering Guarantees

```text
Implement the message sending flow. I need: messages delivered in order,
no duplicates if the client reconnects, and message delivery confirmation
back to the sender. Handle the case where a user is offline — they should
see messages when they reconnect.
```

The tricky part is not sending messages -- it is handling retries without duplicates. When a client loses connection and reconnects, it might resend a message that already arrived. The solution: every message carries a client-generated UUID as an idempotency key.

```typescript
// ws/handlers/message.ts — Delivery with idempotency

async function handleMessage(ws: AuthenticatedSocket, payload: IncomingMessage) {
  // Deduplicate: check if this client UUID was already processed
  const existing = await db.messages.findByClientId(payload.clientId);
  if (existing) {
    // Already processed — send ack with the existing server ID
    ws.send(JSON.stringify({ type: 'ack', clientId: payload.clientId, serverId: existing.id }));
    return;
  }

  // Persist with server-assigned sequential ID (guarantees ordering)
  const message = await db.messages.create({
    clientId: payload.clientId,
    channelId: payload.channelId,
    senderId: ws.userId,
    content: payload.content,
  });

  // Broadcast to all connected room members
  rooms.broadcast(payload.channelId, {
    type: 'message',
    data: message,
  }, ws.userId);  // exclude sender

  // Ack back to sender with server-assigned ID
  ws.send(JSON.stringify({ type: 'ack', clientId: payload.clientId, serverId: message.id }));
}
```

Reconnection sync is equally important. When a client reconnects, it sends its `last_message_id`. The server returns all newer messages per channel. The client merges with local state using the server-assigned ID as the source of truth -- no duplicates, no gaps.

### Step 4: Add Typing Indicators and Presence

```text
Add typing indicators and online presence. Typing should show "Alex is typing..."
and disappear after 3 seconds of inactivity. Presence should show who's online
in a channel without hammering the database.
```

Typing indicators and presence are ephemeral state -- they should never touch the database. Redis handles both.

**Typing** works with auto-expiry: the client sends a "typing" event, the server broadcasts it to the channel (excluding the sender), and the indicator expires after 3 seconds. A debounce prevents flooding -- max one typing event per 2 seconds per user per channel.

**Presence** uses Redis sets for instant lookups:

```
SADD online:{channel_id} {user_id}    — on connect/join
SREM online:{channel_id} {user_id}    — on disconnect/leave
SMEMBERS online:{channel_id}          — get online users
EXPIRE user:{user_id}:alive 90        — auto-cleanup if server crashes
```

No database writes for presence. Purely in-memory via Redis. Presence changes broadcast to channel members as WebSocket events. A 90-second heartbeat timeout catches the case where a server crashes without cleanly disconnecting its sockets.

### Step 5: Write Integration Tests

```text
Write tests covering: sending a message and receiving it in another client,
reconnection with message sync, duplicate message prevention, and typing
indicator timeout.
```

The test suite covers the critical paths that are easy to get wrong:

- Message sent by user A appears in user B's WebSocket stream
- Messages arrive in server-assigned order regardless of send timing
- Duplicate client UUID is rejected; original message returned
- Reconnecting client receives missed messages since `last_message_id`
- Typing indicator expires after 3 seconds of no re-send
- User marked offline after missing 3 heartbeats
- Offline user gets accurate unread count on reconnect

Each test spins up a real WebSocket server with an in-memory database. No mocks for the WebSocket layer -- the tests verify actual message delivery over real connections.

## Real-World Example

A backend developer at a small logistics company needs dispatchers to message drivers in real time. The existing app is a Next.js dashboard with PostgreSQL and 200 daily active users. Separate messaging apps are creating information gaps -- dispatch instructions get lost in a personal WhatsApp thread, and there is no audit trail.

He scaffolds the WebSocket server, chat schema, and message handlers in a day. Direct messages between dispatchers and drivers go live first. Group channels for team-wide broadcasts follow. Presence tracking lets dispatchers see which drivers are currently online and reachable.

The full chat feature ships in three days. Dispatchers stop using a separate messaging app, every instruction has an audit trail, and the 90-second offline detection means dispatchers immediately know when a driver drops off the network.
