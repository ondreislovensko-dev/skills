---
name: rest-api
description: >-
  Design and build RESTful APIs. Use when a user asks to create a REST API,
  design API endpoints, implement CRUD operations, add authentication to an API,
  handle pagination and filtering, set up API versioning, generate OpenAPI/Swagger
  docs, implement rate limiting, build middleware, handle file uploads, add CORS,
  implement HATEOAS, or structure an Express/Fastify/Koa/Flask/FastAPI backend.
  Covers HTTP methods, status codes, resource modeling, error handling, validation,
  and production deployment patterns.
license: Apache-2.0
compatibility: "Node.js 18+ (Express, Fastify) or Python 3.9+ (FastAPI, Flask)"
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: development
  tags: ["rest", "api", "express", "fastapi", "openapi", "crud"]
---

# REST API

## Overview

Design and build production-grade RESTful APIs following industry conventions. This skill covers resource modeling, HTTP semantics, authentication, validation, pagination, versioning, documentation, error handling, and security — with examples in Express (Node.js) and FastAPI (Python).

## Instructions

### Step 1: Project Setup

**Node.js (Express):**
```bash
mkdir my-api && cd my-api && npm init -y
npm install express cors helmet morgan compression
npm install zod           # Validation
npm install jsonwebtoken bcrypt  # Auth
npm install swagger-jsdoc swagger-ui-express  # Docs
npm install -D typescript @types/express @types/node tsx
```

**Node.js (Fastify):**
```bash
npm install fastify @fastify/cors @fastify/helmet @fastify/rate-limit @fastify/swagger @fastify/swagger-ui
```

**Python (FastAPI):**
```bash
pip install "fastapi[standard]" uvicorn sqlalchemy pydantic-settings python-jose[cryptography] passlib[bcrypt]
```

### Step 2: Resource Design

Map your domain to RESTful resources before writing code:

```
Resource        Endpoint                    Methods
─────────────────────────────────────────────────────
Users           /api/v1/users               GET, POST
User            /api/v1/users/:id           GET, PUT, PATCH, DELETE
User Posts      /api/v1/users/:id/posts     GET
Posts           /api/v1/posts               GET, POST
Post            /api/v1/posts/:id           GET, PUT, PATCH, DELETE
Post Comments   /api/v1/posts/:id/comments  GET, POST
Comment         /api/v1/comments/:id        GET, PATCH, DELETE
```

Resource naming rules:
- **Plural nouns**: `/users`, not `/user` or `/getUsers`
- **Nested for relationships**: `/users/:id/posts` (posts belonging to user)
- **Max 2 levels deep**: Beyond that, use query params or top-level resources
- **No verbs in URLs**: Use HTTP methods instead (`POST /users`, not `/createUser`)
- **Kebab-case**: `/user-profiles`, not `/userProfiles`

### Step 3: HTTP Methods and Status Codes

```
Method   Purpose              Success Code   Body
────────────────────────────────────────────────────
GET      Read resource(s)     200 OK         Resource / collection
POST     Create resource      201 Created    Created resource + Location header
PUT      Full replace         200 OK         Updated resource
PATCH    Partial update       200 OK         Updated resource
DELETE   Remove resource      204 No Content (empty)
```

Important status codes:
```
2xx Success
  200 OK                  — General success
  201 Created             — Resource created (POST)
  204 No Content          — Success with no body (DELETE)

3xx Redirection
  301 Moved Permanently   — Resource URL changed permanently
  304 Not Modified        — Cached version is still valid

4xx Client Error
  400 Bad Request         — Invalid input / validation failed
  401 Unauthorized        — Missing or invalid authentication
  403 Forbidden           — Authenticated but not authorized
  404 Not Found           — Resource doesn't exist
  409 Conflict            — Duplicate or state conflict
  422 Unprocessable Entity— Validation error (semantic)
  429 Too Many Requests   — Rate limit exceeded

5xx Server Error
  500 Internal Server Error— Unhandled server error
  503 Service Unavailable  — Maintenance or overload
```

### Step 4: Express API Implementation

```javascript
// src/app.js
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import morgan from 'morgan';
import compression from 'compression';
import { errorHandler } from './middleware/errorHandler.js';
import { notFound } from './middleware/notFound.js';
import usersRouter from './routes/users.js';
import postsRouter from './routes/posts.js';

const app = express();

// Security and utility middleware
app.use(helmet());
app.use(cors({ origin: process.env.ALLOWED_ORIGINS?.split(',') || '*' }));
app.use(compression());
app.use(morgan('combined'));
app.use(express.json({ limit: '10kb' }));

// Routes
app.use('/api/v1/users', usersRouter);
app.use('/api/v1/posts', postsRouter);

// Health check
app.get('/health', (req, res) => res.json({ status: 'ok', timestamp: new Date().toISOString() }));

// Error handling (must be last)
app.use(notFound);
app.use(errorHandler);

export default app;
```

```javascript
// src/routes/users.js
import { Router } from 'express';
import { z } from 'zod';
import { validate } from '../middleware/validate.js';
import { authenticate, authorize } from '../middleware/auth.js';
import * as usersController from '../controllers/users.js';

const router = Router();

const createUserSchema = z.object({
  body: z.object({
    email: z.string().email(),
    name: z.string().min(2).max(100),
    password: z.string().min(8).max(128),
    role: z.enum(['user', 'admin']).default('user'),
  }),
});

const listUsersSchema = z.object({
  query: z.object({
    page: z.coerce.number().int().positive().default(1),
    limit: z.coerce.number().int().min(1).max(100).default(20),
    sort: z.enum(['name', 'createdAt', '-name', '-createdAt']).default('-createdAt'),
    search: z.string().optional(),
  }),
});

const updateUserSchema = z.object({
  body: z.object({
    name: z.string().min(2).max(100).optional(),
    avatar: z.string().url().optional(),
  }).refine(data => Object.keys(data).length > 0, { message: 'At least one field required' }),
  params: z.object({ id: z.string().uuid() }),
});

router.get('/',       authenticate, validate(listUsersSchema), usersController.list);
router.post('/',      validate(createUserSchema),              usersController.create);
router.get('/:id',    authenticate, usersController.getOne);
router.patch('/:id',  authenticate, validate(updateUserSchema), usersController.update);
router.delete('/:id', authenticate, authorize('admin'),        usersController.remove);

export default router;
```

```javascript
// src/controllers/users.js
import { AppError } from '../utils/AppError.js';
import db from '../db.js';

export async function list(req, res) {
  const { page, limit, sort, search } = req.query;
  const offset = (page - 1) * limit;

  const orderBy = sort.startsWith('-')
    ? { [sort.slice(1)]: 'desc' }
    : { [sort]: 'asc' };

  const where = search ? { name: { contains: search, mode: 'insensitive' } } : {};

  const [users, total] = await Promise.all([
    db.user.findMany({ where, orderBy, skip: offset, take: limit, select: { id: true, name: true, email: true, avatar: true, createdAt: true } }),
    db.user.count({ where }),
  ]);

  res.json({
    data: users,
    meta: {
      page,
      limit,
      total,
      totalPages: Math.ceil(total / limit),
    },
  });
}

export async function create(req, res) {
  const existing = await db.user.findUnique({ where: { email: req.body.email } });
  if (existing) throw new AppError(409, 'Email already registered');

  const user = await db.user.create({
    data: { ...req.body, password: await hashPassword(req.body.password) },
    select: { id: true, name: true, email: true, createdAt: true },
  });

  res.status(201)
    .location(`/api/v1/users/${user.id}`)
    .json({ data: user });
}

export async function getOne(req, res) {
  const user = await db.user.findUnique({
    where: { id: req.params.id },
    select: { id: true, name: true, email: true, avatar: true, createdAt: true },
  });
  if (!user) throw new AppError(404, 'User not found');
  res.json({ data: user });
}

export async function update(req, res) {
  const user = await db.user.update({
    where: { id: req.params.id },
    data: req.body,
    select: { id: true, name: true, email: true, avatar: true, createdAt: true },
  });
  res.json({ data: user });
}

export async function remove(req, res) {
  await db.user.delete({ where: { id: req.params.id } });
  res.status(204).end();
}
```

### Step 5: Middleware

```javascript
// src/middleware/validate.js
import { AppError } from '../utils/AppError.js';

export function validate(schema) {
  return (req, res, next) => {
    const result = schema.safeParse({ body: req.body, query: req.query, params: req.params });
    if (!result.success) {
      const errors = result.error.issues.map(i => ({
        field: i.path.join('.'),
        message: i.message,
      }));
      throw new AppError(400, 'Validation failed', errors);
    }
    req.body = result.data.body ?? req.body;
    req.query = result.data.query ?? req.query;
    req.params = result.data.params ?? req.params;
    next();
  };
}

// src/middleware/auth.js
import jwt from 'jsonwebtoken';
import { AppError } from '../utils/AppError.js';

export function authenticate(req, res, next) {
  const header = req.headers.authorization;
  if (!header?.startsWith('Bearer ')) throw new AppError(401, 'Missing token');

  try {
    req.user = jwt.verify(header.slice(7), process.env.JWT_SECRET);
    next();
  } catch {
    throw new AppError(401, 'Invalid token');
  }
}

export function authorize(...roles) {
  return (req, res, next) => {
    if (!roles.includes(req.user.role)) throw new AppError(403, 'Insufficient permissions');
    next();
  };
}

// src/middleware/rateLimit.js
import rateLimit from 'express-rate-limit';

export const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,  // 15 minutes
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: { code: 'RATE_LIMITED', message: 'Too many requests, try again later' } },
});

export const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 10,  // Stricter for auth endpoints
});

// src/middleware/errorHandler.js
export function errorHandler(err, req, res, next) {
  const status = err.statusCode || 500;
  const response = {
    error: {
      code: err.code || 'INTERNAL_ERROR',
      message: status === 500 ? 'Internal server error' : err.message,
    },
  };
  if (err.details) response.error.details = err.details;
  if (process.env.NODE_ENV === 'development' && status === 500) response.error.stack = err.stack;

  console.error(`[${status}] ${err.message}`, status === 500 ? err.stack : '');
  res.status(status).json(response);
}

// src/middleware/notFound.js
export function notFound(req, res) {
  res.status(404).json({ error: { code: 'NOT_FOUND', message: `Route ${req.method} ${req.path} not found` } });
}

// src/utils/AppError.js
export class AppError extends Error {
  constructor(statusCode, message, details = null) {
    super(message);
    this.statusCode = statusCode;
    this.details = details;
  }
}
```

### Step 6: FastAPI Implementation

```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import users, posts

app = FastAPI(
    title="My API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(posts.router, prefix="/api/v1/posts", tags=["posts"])

@app.get("/health")
def health():
    return {"status": "ok"}
```

```python
# app/routes/users.py
from fastapi import APIRouter, Depends, HTTPException, Query
from app.schemas import UserCreate, UserUpdate, UserResponse, PaginatedResponse
from app.dependencies import get_db, get_current_user
from app.services import user_service

router = APIRouter()

@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    sort: str = Query("-created_at"),
    search: str | None = Query(None),
    db=Depends(get_db),
    current_user=Depends(get_current_user),
):
    users, total = await user_service.get_many(db, page=page, limit=limit, sort=sort, search=search)
    return PaginatedResponse(
        data=users,
        meta={"page": page, "limit": limit, "total": total, "total_pages": -(-total // limit)},
    )

@router.post("", response_model=UserResponse, status_code=201)
async def create_user(body: UserCreate, db=Depends(get_db)):
    existing = await user_service.get_by_email(db, body.email)
    if existing:
        raise HTTPException(409, "Email already registered")
    return await user_service.create(db, body)

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db=Depends(get_db), current_user=Depends(get_current_user)):
    user = await user_service.get_by_id(db, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return user

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, body: UserUpdate, db=Depends(get_db), current_user=Depends(get_current_user)):
    return await user_service.update(db, user_id, body)

@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: str, db=Depends(get_db), current_user=Depends(get_current_user)):
    await user_service.delete(db, user_id)
```

```python
# app/schemas.py
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Generic, TypeVar

T = TypeVar("T")

class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=128)

class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    avatar: str | None = None

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    avatar: str | None
    created_at: datetime
    model_config = {"from_attributes": True}

class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int

class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: PaginationMeta
```

### Step 7: Pagination Patterns

**Offset-based** (simple, good for most cases):
```json
GET /api/v1/posts?page=2&limit=20

{
  "data": [...],
  "meta": { "page": 2, "limit": 20, "total": 156, "totalPages": 8 }
}
```

**Cursor-based** (better for real-time feeds, infinite scroll):
```json
GET /api/v1/posts?cursor=eyJpZCI6MTAwfQ&limit=20

{
  "data": [...],
  "meta": { "nextCursor": "eyJpZCI6MTIwfQ", "hasMore": true }
}
```

### Step 8: Filtering and Sorting

```
GET /api/v1/posts?status=published&tag=javascript&sort=-createdAt&fields=id,title,author
```

Common query parameters:
- `sort=-createdAt,title` — comma-separated, `-` prefix for descending
- `fields=id,title,author` — sparse fieldsets (return only requested fields)
- `search=keyword` — full-text search
- `status=active` — exact match filter
- `createdAfter=2024-01-01` — range filter
- `page=1&limit=20` — pagination

### Step 9: OpenAPI Documentation

**Express (swagger-jsdoc):**
```javascript
import swaggerJsdoc from 'swagger-jsdoc';
import swaggerUi from 'swagger-ui-express';

const spec = swaggerJsdoc({
  definition: {
    openapi: '3.0.0',
    info: { title: 'My API', version: '1.0.0' },
    servers: [{ url: '/api/v1' }],
    components: {
      securitySchemes: {
        bearerAuth: { type: 'http', scheme: 'bearer', bearerFormat: 'JWT' },
      },
    },
  },
  apis: ['./src/routes/*.js'],
});

app.use('/api/docs', swaggerUi.serve, swaggerUi.setup(spec));
```

**FastAPI:** Auto-generates OpenAPI at `/api/docs` (Swagger UI) and `/api/redoc` (ReDoc) — no setup needed.

### Step 10: Versioning

**URL path versioning** (recommended):
```
/api/v1/users
/api/v2/users
```

**Header versioning:**
```
Accept: application/vnd.myapi.v2+json
```

Strategy: Run v1 and v2 in parallel during migration. Deprecate v1 with headers:
```javascript
app.use('/api/v1', (req, res, next) => {
  res.set('Deprecation', 'true');
  res.set('Sunset', 'Sat, 01 Mar 2025 00:00:00 GMT');
  res.set('Link', '</api/v2>; rel="successor-version"');
  next();
});
```

### Step 11: File Uploads

```javascript
import multer from 'multer';

const upload = multer({
  limits: { fileSize: 5 * 1024 * 1024 },  // 5MB
  fileFilter: (req, file, cb) => {
    const allowed = ['image/jpeg', 'image/png', 'image/webp'];
    cb(null, allowed.includes(file.mimetype));
  },
  storage: multer.memoryStorage(),
});

router.post('/:id/avatar', authenticate, upload.single('avatar'), async (req, res) => {
  const url = await uploadToS3(req.file.buffer, req.file.mimetype);
  const user = await db.user.update({ where: { id: req.params.id }, data: { avatar: url } });
  res.json({ data: user });
});
```

## Best Practices

1. **Consistent response format** — always wrap in `{ data: ... }` or `{ error: ... }`
2. **Validate all input** — never trust request body, query, or params
3. **Use proper status codes** — 201 for creation, 204 for delete, 409 for conflicts
4. **Include Location header** — on 201 responses, point to the created resource
5. **Pagination by default** — never return unbounded collections
6. **Rate limit everything** — stricter limits on auth endpoints
7. **CORS configured explicitly** — never use `*` in production
8. **Idempotent PUT/DELETE** — calling twice produces the same result
9. **Error responses include machine-readable codes** — `VALIDATION_FAILED`, not just messages
10. **Version from day one** — `/api/v1/` costs nothing and saves future pain

## Common Pitfalls

- **Verbs in URLs**: `POST /api/createUser` → `POST /api/v1/users`
- **200 for everything**: Use specific codes — clients rely on them
- **No validation**: Trust nothing from the client, validate and sanitize
- **Exposing internal errors**: Never leak stack traces or DB errors in production
- **Ignoring Accept/Content-Type**: Respect content negotiation headers
- **Not handling concurrent updates**: Use ETags or version fields for optimistic locking
- **Sync-only in Node.js**: Use async handlers and proper error forwarding with `express-async-errors`
