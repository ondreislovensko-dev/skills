---
name: rate-limiter
description: >-
  Implement rate limiting and API abuse protection for web applications and APIs.
  Use when you need to add request throttling, IP-based blocking, sliding window
  counters, token bucket algorithms, or API key usage quotas. Trigger words:
  rate limit, throttle, API abuse, request quota, DDoS protection, brute force
  prevention, request flooding, API gateway limits.
license: Apache-2.0
compatibility: "Node.js 18+ or Python 3.9+; Redis recommended for distributed setups"
metadata:
  author: carlos
  version: "1.0.0"
  category: development
  tags: ["rate-limiting", "api-security", "throttling", "abuse-prevention"]
---

# Rate Limiter

## Overview

This skill helps you design and implement rate limiting strategies for APIs and web applications. It covers algorithm selection (token bucket, sliding window, fixed window), storage backends (in-memory, Redis, database), response handling, and monitoring. Use it when your API needs protection against abuse, brute-force attacks, or traffic spikes.

## Instructions

When the user asks about rate limiting or API abuse protection, follow this process:

### 1. Assess the Requirements

Ask or determine:
- What type of application (REST API, GraphQL, WebSocket)?
- What framework (Express, FastAPI, Django, Spring Boot)?
- Expected traffic volume (requests per second)?
- Do they need distributed rate limiting (multiple instances)?
- What should happen when limits are exceeded (429 response, queue, degrade)?

### 2. Choose the Algorithm

- **Fixed Window**: Simple, but allows burst at window boundaries. Good for basic quotas.
- **Sliding Window Log**: Precise, but memory-intensive. Good for strict compliance.
- **Sliding Window Counter**: Balance of precision and efficiency. Best general choice.
- **Token Bucket**: Allows controlled bursts. Best for APIs with variable traffic.
- **Leaky Bucket**: Smooths traffic. Best for downstream protection.

### 3. Implement the Solution

Generate code that includes:
- Middleware/decorator for the target framework
- Key extraction (IP, API key, user ID, or composite)
- Storage layer (in-memory for single instance, Redis for distributed)
- Response headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset, Retry-After)
- Configurable limits per endpoint or tier
- Bypass allowlist for health checks and internal services

### 4. Add Abuse Detection

Beyond simple rate limiting, implement:
- Progressive penalties (increasing cooldown for repeat offenders)
- Pattern detection (rapid sequential endpoint scanning)
- Geographic anomaly detection (sudden origin changes)
- Request fingerprinting (beyond IP — user agent, headers pattern)

### 5. Set Up Monitoring

- Log rate limit events with key, endpoint, and timestamp
- Track metrics: total requests, limited requests, unique keys hitting limits
- Alert thresholds: when block rate exceeds 10% of traffic

## Examples

### Example 1: Express.js API with Redis-backed sliding window

**User prompt:**
```
Add rate limiting to my Express API. I have 3 tiers: free (100 req/hour), pro (1000 req/hour), enterprise (10000 req/hour). We run 4 instances behind a load balancer.
```

**Agent output:**

```javascript
// middleware/rateLimiter.js
const Redis = require('ioredis');
const redis = new Redis(process.env.REDIS_URL);

const TIER_LIMITS = {
  free: { max: 100, window: 3600 },
  pro: { max: 1000, window: 3600 },
  enterprise: { max: 10000, window: 3600 },
};

async function rateLimiter(req, res, next) {
  const apiKey = req.headers['x-api-key'];
  if (!apiKey) return res.status(401).json({ error: 'API key required' });

  const tier = await getTierForKey(apiKey);
  const limits = TIER_LIMITS[tier] || TIER_LIMITS.free;
  const key = `ratelimit:${apiKey}`;
  const now = Date.now();
  const windowStart = now - limits.window * 1000;

  const multi = redis.multi();
  multi.zremrangebyscore(key, 0, windowStart);
  multi.zadd(key, now, `${now}:${crypto.randomUUID()}`);
  multi.zcard(key);
  multi.expire(key, limits.window);

  const results = await multi.exec();
  const requestCount = results[2][1];

  res.set({
    'X-RateLimit-Limit': limits.max,
    'X-RateLimit-Remaining': Math.max(0, limits.max - requestCount),
    'X-RateLimit-Reset': Math.ceil((now + limits.window * 1000) / 1000),
  });

  if (requestCount > limits.max) {
    res.set('Retry-After', limits.window);
    return res.status(429).json({
      error: 'Rate limit exceeded',
      retryAfter: limits.window,
    });
  }

  next();
}
```

### Example 2: FastAPI with token bucket and abuse detection

**User prompt:**
```
My FastAPI app is getting hit by scrapers. Add rate limiting with automatic IP blocking for repeat offenders.
```

**Agent output:**

```python
# middleware/rate_limiter.py
import time
import asyncio
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def consume(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

class AbuseDetector:
    def __init__(self):
        self.violations = defaultdict(list)
        self.blocked = {}

    def record_violation(self, ip: str):
        now = time.monotonic()
        self.violations[ip].append(now)
        recent = [t for t in self.violations[ip] if now - t < 3600]
        self.violations[ip] = recent
        if len(recent) >= 10:
            block_duration = min(3600 * 24, 300 * (2 ** (len(recent) // 10)))
            self.blocked[ip] = now + block_duration

    def is_blocked(self, ip: str) -> bool:
        if ip in self.blocked:
            if time.monotonic() < self.blocked[ip]:
                return True
            del self.blocked[ip]
        return False
```

## Guidelines

- Always return standard rate limit headers (RFC 6585 and draft-ietf-httpapi-ratelimit-headers)
- Use 429 Too Many Requests, never 403 for rate limiting
- Include Retry-After header with seconds until reset
- For distributed systems, Redis sorted sets give the best precision-to-performance ratio
- Never rate limit health check endpoints — add an allowlist
- Log blocked requests for security review but avoid logging full request bodies
- Test with load testing tools (k6, artillery) before deploying
- Consider separate limits per endpoint — login endpoints need stricter limits than read endpoints
- For WebSocket, implement per-connection message rate limiting separately
