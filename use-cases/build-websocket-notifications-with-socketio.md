---
title: Build Real-Time WebSocket Notifications with Socket.IO
slug: build-websocket-notifications-with-socketio
description: >-
  Add real-time notifications to your web app using Socket.IO — push updates
  for new messages, task assignments, comments, and system alerts without
  polling, with presence indicators and typing status.
skills:
  - socketio
  - redis
  - websocket-builder
category: development
tags:
  - websocket
  - notifications
  - realtime
  - socketio
  - presence
---

# Build Real-Time WebSocket Notifications with Socket.IO

Amara's project management app uses polling — every 30 seconds, every tab hits the API asking "anything new?" With 500 concurrent users and 3 tabs each, that's 3,000 requests per minute that usually return nothing. She wants real-time push: when someone assigns a task, the assignee sees it instantly. When someone comments, the thread updates live. When teammates are online, you see green dots. No more polling.

## Step 1: Socket.IO Server with Auth

```typescript
// src/realtime/server.ts
import { Server } from "socket.io";
import { createAdapter } from "@socket.io/redis-adapter";
import { createClient } from "redis";
import { verifyToken } from "../auth";

const pub = createClient({ url: process.env.REDIS_URL });
const sub = pub.duplicate();
await Promise.all([pub.connect(), sub.connect()]);

export const io = new Server({
  cors: { origin: process.env.CLIENT_URL },
  adapter: createAdapter(pub, sub),
});

// Authentication middleware
io.use(async (socket, next) => {
  const token = socket.handshake.auth.token;
  if (!token) return next(new Error("Authentication required"));

  try {
    const user = await verifyToken(token);
    socket.data.userId = user.id;
    socket.data.orgId = user.orgId;
    socket.data.userName = user.name;
    next();
  } catch {
    next(new Error("Invalid token"));
  }
});

io.on("connection", (socket) => {
  const { userId, orgId } = socket.data;

  // Join personal and org rooms
  socket.join(`user:${userId}`);
  socket.join(`org:${orgId}`);

  // Track presence
  setUserOnline(userId, orgId);
  socket.to(`org:${orgId}`).emit("presence:online", { userId });

  socket.on("disconnect", () => {
    setUserOffline(userId, orgId);
    socket.to(`org:${orgId}`).emit("presence:offline", { userId });
  });

  // Typing indicators
  socket.on("typing:start", ({ channelId }) => {
    socket.to(`channel:${channelId}`).emit("typing:start", {
      userId,
      userName: socket.data.userName,
    });
  });

  socket.on("typing:stop", ({ channelId }) => {
    socket.to(`channel:${channelId}`).emit("typing:stop", { userId });
  });

  // Join specific channels/projects
  socket.on("channel:join", ({ channelId }) => {
    socket.join(`channel:${channelId}`);
  });

  socket.on("channel:leave", ({ channelId }) => {
    socket.leave(`channel:${channelId}`);
  });
});
```

## Step 2: Notification Emitter Service

```typescript
// src/realtime/notify.ts
import { io } from "./server";
import { redis } from "../lib/redis";

interface Notification {
  id: string;
  type: "task_assigned" | "comment_added" | "mention" | "status_changed" | "system";
  title: string;
  body: string;
  actionUrl?: string;
  actorId: string;
  actorName: string;
  createdAt: string;
}

export function notifyUser(userId: string, notification: Notification) {
  io.to(`user:${userId}`).emit("notification", notification);

  // Also store in Redis for unread count
  redis.lpush(`notifications:${userId}`, JSON.stringify(notification));
  redis.ltrim(`notifications:${userId}`, 0, 99); // Keep last 100
  redis.incr(`unread:${userId}`);
}

export function notifyOrg(orgId: string, event: string, data: unknown) {
  io.to(`org:${orgId}`).emit(event, data);
}

export function notifyChannel(channelId: string, event: string, data: unknown) {
  io.to(`channel:${channelId}`).emit(event, data);
}

// Use from anywhere in your API:
// When a task is assigned:
export function onTaskAssigned(task: Task, assignerId: string, assignerName: string) {
  notifyUser(task.assigneeId, {
    id: crypto.randomUUID(),
    type: "task_assigned",
    title: "New task assigned",
    body: `${assignerName} assigned you "${task.title}"`,
    actionUrl: `/projects/${task.projectId}/tasks/${task.id}`,
    actorId: assignerId,
    actorName: assignerName,
    createdAt: new Date().toISOString(),
  });

  // Also update the project channel with live task list
  notifyChannel(`project:${task.projectId}`, "task:updated", {
    task: sanitizeTask(task),
  });
}
```

## Step 3: Presence System

```typescript
// src/realtime/presence.ts
import { redis } from "../lib/redis";

export async function setUserOnline(userId: string, orgId: string) {
  await redis.sadd(`online:${orgId}`, userId);
  await redis.setex(`lastseen:${userId}`, 86400, Date.now().toString());
}

export async function setUserOffline(userId: string, orgId: string) {
  await redis.srem(`online:${orgId}`, userId);
  await redis.setex(`lastseen:${userId}`, 86400, Date.now().toString());
}

export async function getOnlineUsers(orgId: string): Promise<string[]> {
  return redis.smembers(`online:${orgId}`);
}

export async function getLastSeen(userId: string): Promise<number | null> {
  const ts = await redis.get(`lastseen:${userId}`);
  return ts ? parseInt(ts) : null;
}
```

## Step 4: Client-Side Hook

```typescript
// src/hooks/useRealtimeNotifications.ts
import { useEffect, useState, useCallback } from "react";
import { io, Socket } from "socket.io-client";

let socket: Socket | null = null;

export function useRealtimeNotifications(token: string) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [onlineUsers, setOnlineUsers] = useState<Set<string>>(new Set());

  useEffect(() => {
    socket = io(process.env.NEXT_PUBLIC_WS_URL!, {
      auth: { token },
      reconnection: true,
      reconnectionDelay: 1000,
    });

    socket.on("notification", (notif: Notification) => {
      setNotifications((prev) => [notif, ...prev].slice(0, 50));
      setUnreadCount((c) => c + 1);

      // Browser notification if tab is not focused
      if (document.hidden && Notification.permission === "granted") {
        new Notification(notif.title, { body: notif.body });
      }
    });

    socket.on("presence:online", ({ userId }) => {
      setOnlineUsers((prev) => new Set(prev).add(userId));
    });

    socket.on("presence:offline", ({ userId }) => {
      setOnlineUsers((prev) => {
        const next = new Set(prev);
        next.delete(userId);
        return next;
      });
    });

    return () => { socket?.disconnect(); };
  }, [token]);

  const markAllRead = useCallback(() => setUnreadCount(0), []);

  return { notifications, unreadCount, onlineUsers, markAllRead };
}
```

## Summary

Amara eliminated 3,000 polling requests per minute. Notifications are now instant — task assignments, comments, and mentions appear in real-time. Green presence dots show who's online, and typing indicators make chat feel alive. Redis pub/sub through Socket.IO's adapter means the system scales horizontally — add more server instances and they all share the same event bus. Unread counts persist across reconnections via Redis, and browser notifications catch users even when the tab is in the background.
