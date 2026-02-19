---
name: redis
category: devops
version: 1.0.0
description: >-
  Build applications with Redis — caching, session storage, pub/sub, streams,
  rate limiting, leaderboards, and queues. Use when tasks involve in-memory
  data storage, real-time messaging, distributed locking, or performance
  optimization with caching layers.
author: terminal-skills
tags: [redis, caching, database, pub-sub, queues, performance]
---

# Redis

Build fast, scalable applications with Redis as a cache, message broker, session store, or real-time data engine.

## Setup

### Docker (quickstart)

```bash
# Redis 7 with persistence
docker run -d --name redis -p 6379:6379 \
  -v redis-data:/data \
  redis:7-alpine redis-server --appendonly yes --requirepass "your-password"
```

### Connection

```python
"""redis_client.py — Redis connection with connection pooling."""
import redis

# Single connection
r = redis.Redis(host="localhost", port=6379, password="your-password", db=0,
                decode_responses=True)  # Auto-decode bytes to strings

# Connection pool (recommended for production)
pool = redis.ConnectionPool(
    host="localhost", port=6379, password="your-password",
    max_connections=20,  # Match your app's concurrency
    decode_responses=True,
)
r = redis.Redis(connection_pool=pool)

# Verify connection
r.ping()  # Returns True
```

```javascript
// redis-client.js — Node.js connection with ioredis
import Redis from 'ioredis';

const redis = new Redis({
  host: 'localhost',
  port: 6379,
  password: 'your-password',
  maxRetriesPerRequest: 3,
  retryStrategy: (times) => Math.min(times * 50, 2000), // Exponential backoff, cap at 2s
});
```

## Caching Patterns

### Cache-Aside (most common)

```python
"""cache_aside.py — Cache-aside pattern with automatic expiration."""
import json

def get_user(user_id: int) -> dict:
    """Fetch user from cache, falling back to database.

    Args:
        user_id: The user's ID.

    Returns:
        User dict from cache or database.
    """
    cache_key = f"user:{user_id}"
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)

    # Cache miss — fetch from database
    user = db.query("SELECT * FROM users WHERE id = %s", user_id)
    r.setex(cache_key, 3600, json.dumps(user))  # Cache for 1 hour
    return user

def update_user(user_id: int, data: dict):
    """Update user in database and invalidate cache.

    Args:
        user_id: The user's ID.
        data: Fields to update.
    """
    db.execute("UPDATE users SET ... WHERE id = %s", user_id)
    r.delete(f"user:{user_id}")  # Invalidate — next read repopulates
```

### Write-Through Cache

```python
"""write_through.py — Write-through: update cache and DB together."""

def save_product(product_id: str, data: dict):
    """Save product to both database and cache atomically.

    Args:
        product_id: Product identifier.
        data: Product data dict.
    """
    # Write to DB first (source of truth)
    db.execute("INSERT INTO products ... ON CONFLICT UPDATE ...", data)

    # Then update cache
    r.setex(f"product:{product_id}", 7200, json.dumps(data))  # 2h TTL
```

## Session Storage

```python
"""session_store.py — HTTP session storage in Redis."""
import secrets, json

SESSION_TTL = 86400  # 24 hours

def create_session(user_id: int, metadata: dict = None) -> str:
    """Create a new session and return the session token.

    Args:
        user_id: Authenticated user's ID.
        metadata: Optional session metadata (IP, user-agent, etc.).
    """
    token = secrets.token_urlsafe(32)
    session_data = {"user_id": user_id, "created_at": time.time(), **(metadata or {})}
    r.setex(f"session:{token}", SESSION_TTL, json.dumps(session_data))
    # Track active sessions per user for "log out everywhere"
    r.sadd(f"user_sessions:{user_id}", token)
    return token

def get_session(token: str) -> dict | None:
    """Validate and return session data, extending TTL on access.

    Args:
        token: Session token from cookie/header.
    """
    data = r.get(f"session:{token}")
    if not data:
        return None
    r.expire(f"session:{token}", SESSION_TTL)  # Sliding expiration
    return json.loads(data)

def destroy_all_sessions(user_id: int):
    """Invalidate all sessions for a user (password change, security breach).

    Args:
        user_id: The user whose sessions to destroy.
    """
    tokens = r.smembers(f"user_sessions:{user_id}")
    if tokens:
        r.delete(*[f"session:{t}" for t in tokens])
    r.delete(f"user_sessions:{user_id}")
```

## Rate Limiting

### Sliding Window

```python
"""rate_limiter.py — Sliding window rate limiter using sorted sets."""
import time

def is_rate_limited(key: str, limit: int, window_seconds: int) -> bool:
    """Check if a key has exceeded its rate limit.

    Args:
        key: Identifier (e.g., IP address, API key, user ID).
        limit: Maximum requests allowed in the window.
        window_seconds: Window size in seconds.

    Returns:
        True if rate limited, False if request is allowed.
    """
    now = time.time()
    window_start = now - window_seconds
    pipe = r.pipeline()
    rk = f"ratelimit:{key}"

    pipe.zremrangebyscore(rk, 0, window_start)  # Remove expired entries
    pipe.zadd(rk, {f"{now}": now})              # Add current request
    pipe.zcard(rk)                               # Count requests in window
    pipe.expire(rk, window_seconds)              # Auto-cleanup

    results = pipe.execute()
    count = results[2]
    return count > limit
```

### Token Bucket (smoother)

```python
"""token_bucket.py — Token bucket rate limiter using Lua script."""

TOKEN_BUCKET_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])  -- tokens per second
local now = tonumber(ARGV[3])

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1]) or capacity
local last_refill = tonumber(data[2]) or now

-- Refill tokens based on elapsed time
local elapsed = now - last_refill
tokens = math.min(capacity, tokens + elapsed * refill_rate)

if tokens >= 1 then
    tokens = tokens - 1
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    redis.call('EXPIRE', key, math.ceil(capacity / refill_rate) + 1)
    return 1  -- Allowed
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', now)
    return 0  -- Denied
end
"""

# Register the script once
bucket_sha = r.script_load(TOKEN_BUCKET_SCRIPT)

def check_token_bucket(key: str, capacity: int = 10, refill_rate: float = 1.0) -> bool:
    """Check token bucket rate limiter.

    Args:
        key: Identifier for the bucket.
        capacity: Maximum tokens (burst size).
        refill_rate: Tokens added per second.
    """
    return r.evalsha(bucket_sha, 1, f"bucket:{key}", capacity, refill_rate, time.time()) == 1
```

## Pub/Sub

```python
"""pubsub.py — Real-time messaging with Redis pub/sub."""
import threading

def publish_event(channel: str, event: dict):
    """Publish an event to a channel.

    Args:
        channel: Channel name (e.g., "notifications:user:123").
        event: Event data dict — serialized to JSON.
    """
    r.publish(channel, json.dumps(event))

def subscribe_to_events(pattern: str, callback):
    """Subscribe to channels matching a pattern.

    Args:
        pattern: Glob pattern (e.g., "notifications:*").
        callback: Function called with (channel, data) for each message.
    """
    ps = r.pubsub()
    ps.psubscribe(pattern)

    def listener():
        for msg in ps.listen():
            if msg["type"] == "pmessage":
                callback(msg["channel"], json.loads(msg["data"]))

    thread = threading.Thread(target=listener, daemon=True)
    thread.start()
    return ps  # Return for cleanup: ps.punsubscribe()
```

## Streams (persistent messaging)

Unlike pub/sub, streams persist messages and support consumer groups:

```python
"""streams.py — Redis Streams for reliable event processing."""

def add_to_stream(stream: str, data: dict, maxlen: int = 10000) -> str:
    """Add an event to a stream with automatic trimming.

    Args:
        stream: Stream name (e.g., "events:orders").
        data: Event data as flat dict (values must be strings).
        maxlen: Approximate max stream length for memory management.

    Returns:
        Message ID (e.g., "1708123456789-0").
    """
    return r.xadd(stream, data, maxlen=maxlen, approximate=True)

def create_consumer_group(stream: str, group: str):
    """Create a consumer group, starting from new messages.

    Args:
        stream: Stream name.
        group: Consumer group name.
    """
    try:
        r.xgroup_create(stream, group, id="$", mkstream=True)
    except redis.ResponseError as e:
        if "BUSYGROUP" not in str(e):  # Group already exists — that's fine
            raise

def consume_stream(stream: str, group: str, consumer: str,
                   handler, batch_size: int = 10):
    """Consume messages from a stream with acknowledgment.

    Args:
        stream: Stream name.
        group: Consumer group name.
        consumer: This consumer's unique name.
        handler: Function called with (message_id, data) for each message.
        batch_size: Messages to read per iteration.
    """
    while True:
        messages = r.xreadgroup(group, consumer, {stream: ">"},
                                count=batch_size, block=5000)  # Block 5s
        if not messages:
            continue
        for _, entries in messages:
            for msg_id, data in entries:
                try:
                    handler(msg_id, data)
                    r.xack(stream, group, msg_id)
                except Exception as e:
                    print(f"Failed to process {msg_id}: {e}")
                    # Message stays pending — will be retried or claimed
```

## Distributed Locking

```python
"""distributed_lock.py — Distributed lock using Redis (Redlock pattern)."""

def acquire_lock(name: str, timeout: int = 10) -> str | None:
    """Acquire a distributed lock.

    Args:
        name: Lock name (e.g., "process:invoice:12345").
        timeout: Lock expiration in seconds (prevents deadlocks).

    Returns:
        Lock token if acquired, None if already held.
    """
    token = secrets.token_urlsafe(16)
    acquired = r.set(f"lock:{name}", token, nx=True, ex=timeout)
    return token if acquired else None

# Lua script ensures atomic check-and-delete (only owner can release)
RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""

def release_lock(name: str, token: str) -> bool:
    """Release a lock (only if we own it).

    Args:
        name: Lock name.
        token: Token returned by acquire_lock.
    """
    return r.eval(RELEASE_SCRIPT, 1, f"lock:{name}", token) == 1
```

## Leaderboards

```python
"""leaderboard.py — Real-time leaderboard using sorted sets."""

def update_score(board: str, user_id: str, score: float):
    """Set or update a user's score on a leaderboard.

    Args:
        board: Leaderboard name.
        user_id: Player/user identifier.
        score: New score value.
    """
    r.zadd(f"leaderboard:{board}", {user_id: score})

def get_top(board: str, count: int = 10) -> list[tuple[str, float]]:
    """Get top N users by score (highest first).

    Args:
        board: Leaderboard name.
        count: Number of top entries to return.
    """
    return r.zrevrange(f"leaderboard:{board}", 0, count - 1, withscores=True)

def get_rank(board: str, user_id: str) -> int | None:
    """Get a user's rank (0-based, highest score = rank 0).

    Args:
        board: Leaderboard name.
        user_id: Player/user identifier.
    """
    rank = r.zrevrank(f"leaderboard:{board}", user_id)
    return rank  # None if user not on board
```

## Production Configuration

```
# redis.conf — production settings
maxmemory 2gb
maxmemory-policy allkeys-lru      # Evict least recently used keys when memory full
appendonly yes                     # AOF persistence for durability
appendfsync everysec               # Flush to disk every second (balance speed/safety)
tcp-keepalive 300
timeout 0
databases 16
```

## Guidelines

- Use `SETEX`/`SET ... EX` with TTLs for all cache keys -- keys without expiration leak memory
- Pipeline multiple commands when doing batch operations -- reduces round trips
- Use Lua scripts for atomic multi-step operations (check-and-set, compare-and-delete)
- Prefer Streams over pub/sub when message persistence matters -- pub/sub drops messages if no subscriber is listening
- Key naming convention: use colons as separators (`user:123:profile`, `cache:product:456`)
- Monitor memory usage with `INFO memory` -- Redis is in-memory, running out kills the process
- Use `SCAN` instead of `KEYS *` in production -- `KEYS` blocks the server on large datasets
- Connection pooling is essential -- creating a new connection per request adds 1-2ms latency
- Redis is single-threaded for commands -- one slow Lua script blocks everything
