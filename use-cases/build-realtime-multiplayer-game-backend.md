---
title: Build a Real-Time Multiplayer Game Backend
slug: build-realtime-multiplayer-game-backend
description: >-
  Build a WebSocket-based multiplayer game server with room management,
  game state synchronization, lag compensation, and reconnection handling
  using Socket.IO and Redis.
skills:
  - socketio
  - redis
  - docker-compose
  - websocket-builder
category: development
tags:
  - gamedev
  - websocket
  - realtime
  - multiplayer
  - backend
---

# Build a Real-Time Multiplayer Game Backend

Yuki is building a browser-based multiplayer trivia game for up to 8 players per room. Players join a room, answer questions in real-time, see live scoreboards, and get results instantly. She needs WebSocket connections for low-latency communication, room management so games don't leak into each other, and reconnection handling because mobile players lose connection constantly.

## Step 1: Server Setup with Socket.IO and Redis

```typescript
// src/server.ts
import { createServer } from "http";
import { Server } from "socket.io";
import { createAdapter } from "@socket.io/redis-adapter";
import { createClient } from "redis";

const httpServer = createServer();

const pubClient = createClient({ url: process.env.REDIS_URL });
const subClient = pubClient.duplicate();
await Promise.all([pubClient.connect(), subClient.connect()]);

const io = new Server(httpServer, {
  cors: { origin: process.env.CLIENT_URL, methods: ["GET", "POST"] },
  adapter: createAdapter(pubClient, subClient),
  pingInterval: 10000,
  pingTimeout: 5000,
});

httpServer.listen(3001, () => console.log("Game server on :3001"));
export { io };
```

## Step 2: Room and Game State Management

```typescript
// src/game/room.ts
import { Redis } from "ioredis";

const redis = new Redis(process.env.REDIS_URL!);

interface GameRoom {
  id: string;
  hostId: string;
  players: Player[];
  status: "waiting" | "playing" | "finished";
  currentQuestion: number;
  questions: Question[];
  scores: Record<string, number>;
  roundDeadline: number | null;
}

interface Player {
  id: string;
  socketId: string;
  name: string;
  avatar: string;
  connected: boolean;
}

export async function createRoom(hostId: string, hostName: string): Promise<GameRoom> {
  const roomId = generateRoomCode(); // e.g., "ABCD"
  const room: GameRoom = {
    id: roomId,
    hostId,
    players: [{ id: hostId, socketId: "", name: hostName, avatar: "🎮", connected: true }],
    status: "waiting",
    currentQuestion: -1,
    questions: [],
    scores: { [hostId]: 0 },
    roundDeadline: null,
  };
  await redis.setex(`room:${roomId}`, 7200, JSON.stringify(room)); // 2h TTL
  return room;
}

export async function getRoom(roomId: string): Promise<GameRoom | null> {
  const data = await redis.get(`room:${roomId}`);
  return data ? JSON.parse(data) : null;
}

export async function updateRoom(room: GameRoom): Promise<void> {
  await redis.setex(`room:${room.id}`, 7200, JSON.stringify(room));
}

function generateRoomCode(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  return Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join("");
}
```

## Step 3: Socket Event Handlers

```typescript
// src/game/handlers.ts
import { Server, Socket } from "socket.io";
import { createRoom, getRoom, updateRoom } from "./room";

export function registerHandlers(io: Server) {
  io.on("connection", (socket: Socket) => {
    const playerId = socket.handshake.auth.playerId;

    socket.on("room:create", async ({ playerName }, callback) => {
      const room = await createRoom(playerId, playerName);
      room.players[0].socketId = socket.id;
      await updateRoom(room);
      socket.join(room.id);
      callback({ success: true, roomId: room.id });
    });

    socket.on("room:join", async ({ roomId, playerName }, callback) => {
      const room = await getRoom(roomId);
      if (!room) return callback({ success: false, error: "Room not found" });
      if (room.players.length >= 8) return callback({ success: false, error: "Room full" });
      if (room.status !== "waiting") return callback({ success: false, error: "Game in progress" });

      room.players.push({
        id: playerId,
        socketId: socket.id,
        name: playerName,
        avatar: "🎲",
        connected: true,
      });
      room.scores[playerId] = 0;
      await updateRoom(room);

      socket.join(roomId);
      io.to(roomId).emit("room:playerJoined", {
        players: room.players.map((p) => ({ id: p.id, name: p.name, avatar: p.avatar })),
      });
      callback({ success: true, room: sanitizeRoom(room) });
    });

    socket.on("game:start", async ({ roomId }) => {
      const room = await getRoom(roomId);
      if (!room || room.hostId !== playerId) return;

      room.status = "playing";
      room.questions = await fetchQuestions(10);
      room.currentQuestion = 0;
      room.roundDeadline = Date.now() + 15000; // 15s per question
      await updateRoom(room);

      io.to(roomId).emit("game:started", {
        question: sanitizeQuestion(room.questions[0]),
        questionIndex: 0,
        totalQuestions: room.questions.length,
        deadline: room.roundDeadline,
      });

      // Auto-advance after timeout
      scheduleNextQuestion(io, roomId, 0);
    });

    socket.on("game:answer", async ({ roomId, answer }) => {
      const room = await getRoom(roomId);
      if (!room || room.status !== "playing") return;

      const question = room.questions[room.currentQuestion];
      const isCorrect = answer === question.correctAnswer;
      const timeLeft = Math.max(0, (room.roundDeadline || 0) - Date.now());
      const points = isCorrect ? Math.round(100 + (timeLeft / 15000) * 100) : 0;

      room.scores[playerId] = (room.scores[playerId] || 0) + points;
      await updateRoom(room);

      socket.emit("game:answerResult", { correct: isCorrect, points });
      io.to(roomId).emit("game:scoreUpdate", { scores: room.scores });
    });

    // Reconnection handling
    socket.on("room:reconnect", async ({ roomId }, callback) => {
      const room = await getRoom(roomId);
      if (!room) return callback({ success: false });

      const player = room.players.find((p) => p.id === playerId);
      if (!player) return callback({ success: false });

      player.socketId = socket.id;
      player.connected = true;
      await updateRoom(room);
      socket.join(roomId);

      callback({
        success: true,
        room: sanitizeRoom(room),
        currentQuestion: room.status === "playing" ? sanitizeQuestion(room.questions[room.currentQuestion]) : null,
      });

      io.to(roomId).emit("room:playerReconnected", { playerId, playerName: player.name });
    });

    socket.on("disconnect", async () => {
      // Mark player as disconnected in all their rooms
      const rooms = Array.from(socket.rooms).filter((r) => r !== socket.id);
      for (const roomId of rooms) {
        const room = await getRoom(roomId);
        if (!room) continue;
        const player = room.players.find((p) => p.socketId === socket.id);
        if (player) {
          player.connected = false;
          await updateRoom(room);
          io.to(roomId).emit("room:playerDisconnected", { playerId: player.id, playerName: player.name });
        }
      }
    });
  });
}
```

## Step 4: Client-Side Connection with Auto-Reconnect

```typescript
// src/client/socket.ts
import { io, Socket } from "socket.io-client";

let socket: Socket;
let currentRoomId: string | null = null;

export function connect(playerId: string) {
  socket = io(process.env.NEXT_PUBLIC_GAME_SERVER!, {
    auth: { playerId },
    reconnection: true,
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
  });

  socket.on("connect", () => {
    console.log("Connected:", socket.id);
    if (currentRoomId) {
      socket.emit("room:reconnect", { roomId: currentRoomId }, (res: any) => {
        if (res.success) {
          console.log("Reconnected to room:", currentRoomId);
        }
      });
    }
  });

  return socket;
}
```

## Summary

Yuki has a multiplayer game backend that handles room creation with short codes, real-time question rounds with time-based scoring, and automatic reconnection for flaky mobile connections. Redis stores game state so the server can scale horizontally, and Socket.IO's Redis adapter ensures events reach all players regardless of which server instance they're connected to. The entire system handles the reality of multiplayer: players disconnect, rejoin, and the game keeps going.
