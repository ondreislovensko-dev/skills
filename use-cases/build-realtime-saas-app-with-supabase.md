---
title: "Build a Real-Time SaaS Application with Supabase"
slug: build-realtime-saas-app-with-supabase
description: "Build a multi-tenant SaaS application with Supabase — Postgres with Row-Level Security, authentication, real-time subscriptions, and file storage — without managing any backend infrastructure."
skills: [supabase, auth-system-setup, database-schema-designer]
category: development
tags: [supabase, saas, realtime, authentication, postgres, baas]
---

# Build a Real-Time SaaS Application with Supabase

## The Problem

Marta is a solo developer building a project management tool for freelancers. She has a working React frontend -- the UI is designed, the components are built, the routing works. What she does not have is a backend.

She needs user authentication, a database with proper access control so users only see their own data, real-time updates when team members change tasks, and file storage for attachments. Building this with Node.js and Express means writing auth middleware, designing REST endpoints, setting up a WebSocket server for real-time, managing file uploads to S3, and deploying and maintaining all of it. For a solo developer, that is 4-6 weeks of backend work before building any actual product features.

She needs a backend that handles auth, database, real-time, and storage out of the box -- so she can launch an MVP while competitors are still configuring middleware.

## The Solution

Use **supabase** for the entire backend -- Postgres database with Row-Level Security, built-in authentication, real-time subscriptions, and file storage. Use **auth-system-setup** for designing the auth flow (magic links + Google OAuth), and **database-schema-designer** for the multi-tenant data model.

## Step-by-Step Walkthrough

### Step 1: Design the Multi-Tenant Database Schema

```text
I'm building a project management SaaS for freelancers. I need a multi-tenant schema where each user can create workspaces, invite members, and manage projects with tasks. The schema should support: workspaces (owned by a user, members with roles), projects (belong to a workspace), tasks (belong to a project, assigned to a member, have status and priority), and comments (on tasks, real-time). Design the Supabase schema with proper Row-Level Security so users can only access their own workspaces and data. Use Postgres best practices.
```

Multi-tenancy in Supabase means Row-Level Security (RLS) does the heavy lifting. Every query automatically filters to data the current user has access to -- no middleware, no `WHERE user_id = ?` scattered across your codebase.

The schema uses five tables:

```sql
-- supabase/migrations/20260218_create_schema.sql

CREATE TABLE workspaces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  owner_id UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE workspace_members (
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id),
  role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'member')),
  PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'active'
);

CREATE TABLE tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'todo' CHECK (status IN ('todo', 'in_progress', 'review', 'done')),
  priority TEXT DEFAULT 'medium',
  assignee_id UUID REFERENCES auth.users(id),
  due_date DATE,
  position INTEGER,          -- for drag-and-drop ordering
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
  author_id UUID REFERENCES auth.users(id),
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

RLS policies enforce access at the database level. A user can only see workspaces they belong to, and everything cascades from there:

```sql
-- Workspaces: only members can see them
CREATE POLICY "workspace_member_select" ON workspaces FOR SELECT USING (
  id IN (SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid())
);

-- Tasks: only workspace members can view, assignee or admin can update
CREATE POLICY "task_workspace_select" ON tasks FOR SELECT USING (
  project_id IN (
    SELECT p.id FROM projects p
    JOIN workspace_members wm ON wm.workspace_id = p.workspace_id
    WHERE wm.user_id = auth.uid()
  )
);

-- Comments: workspace members can read and write, but only authors can edit/delete
CREATE POLICY "comment_author_update" ON comments FOR UPDATE USING (
  author_id = auth.uid()
);
```

The migration file totals 247 lines covering 5 tables, 14 RLS policies, triggers for auto-adding the creator as workspace owner, and auto-updating `tasks.updated_at` on changes.

### Step 2: Set Up Authentication with Magic Links and Google OAuth

```text
Configure Supabase auth for my app. I want two sign-in methods: magic link (passwordless email) as the primary method, and Google OAuth as an alternative. After sign-up, auto-create a user profile with their name and avatar from the auth metadata. Set up the auth callback handler for my Next.js app. Show me the complete login page component with both methods.
```

Passwordless magic links are the primary sign-in. No passwords to hash, no reset flows to build, and the conversion rate is higher because users do not abandon signup to think of a password.

The flow for both methods converges at the same callback:

1. User enters email (magic link) or clicks "Sign in with Google"
2. Supabase handles the auth exchange
3. User lands at `/auth/callback` which exchanges the code for a session
4. A database trigger fires on `auth.users` INSERT, creating a profile row:

```sql
-- Auto-create profile on signup
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO profiles (id, email, full_name, avatar_url)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', split_part(NEW.email, '@', 1)),
    NEW.raw_user_meta_data->>'avatar_url'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();
```

Google users get their name and avatar pulled from OAuth metadata. Magic link users get their email prefix as a display name. Either way, the profile exists before the user reaches the dashboard.

The Next.js integration consists of four files: the callback route handler, the login page component, a browser Supabase client, a server Supabase client, and middleware that refreshes the session on every request.

### Step 3: Build the Real-Time Task Board

```text
Create a real-time Kanban task board component. It should: load tasks for a project grouped by status (todo, in_progress, review, done), support drag-and-drop between columns (update status and position), show real-time updates when another team member moves a task or adds a comment, and display an avatar of who's currently viewing the board using Supabase Presence. When a task moves, all connected users should see it move instantly.
```

The Kanban board subscribes to Postgres changes through Supabase real-time. When any user moves a task, every connected client sees it happen instantly:

```typescript
// components/task-board.tsx — Real-time subscriptions

const channel = supabase.channel(`project-${projectId}`);

// Subscribe to task changes (INSERT, UPDATE, DELETE)
channel.on('postgres_changes',
  { event: '*', schema: 'public', table: 'tasks', filter: `project_id=eq.${projectId}` },
  (payload) => {
    if (payload.eventType === 'INSERT') addTaskToColumn(payload.new);
    if (payload.eventType === 'UPDATE') moveTaskBetweenColumns(payload.old, payload.new);
    if (payload.eventType === 'DELETE') removeTaskFromColumn(payload.old);
  }
);

// Track who's viewing the board via Presence
channel.on('presence', { event: 'sync' }, () => {
  setOnlineUsers(channel.presenceState());
});

channel.subscribe(async (status) => {
  if (status === 'SUBSCRIBED') {
    await channel.track({ user_id: user.id, name: user.name, avatar: user.avatar });
  }
});
```

Drag-and-drop uses `@dnd-kit/core`. On drop, the UI moves the card immediately (optimistic update), then fires a Supabase update. RLS ensures only workspace members can move tasks. If the update fails -- maybe the user's permission was revoked -- the card snaps back.

The presence feature shows colored avatars of everyone viewing the board in the header. "Dani is viewing" appears next to their avatar. This is purely ephemeral state managed by Supabase Presence -- no database writes.

### Step 4: Add File Attachments with Storage

```text
Add file attachment support to tasks. Users should be able to upload files (images, PDFs, documents) up to 10MB per file. Store files in a Supabase storage bucket organized by workspace/project/task. Show image previews inline in the task detail view. Only workspace members should be able to view and upload files. Add drag-and-drop upload to the task detail panel.
```

Supabase Storage handles files the same way RLS handles data -- policies enforce access at the bucket level:

```sql
-- Storage policies for task-attachments bucket

-- Only workspace members can view files
CREATE POLICY "attachment_read" ON storage.objects FOR SELECT USING (
  bucket_id = 'task-attachments' AND
  (storage.foldername(name))[1]::uuid IN (
    SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
  )
);

-- Only workspace members can upload, with size and type restrictions
CREATE POLICY "attachment_upload" ON storage.objects FOR INSERT WITH CHECK (
  bucket_id = 'task-attachments' AND
  (storage.foldername(name))[1]::uuid IN (
    SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
  )
);
```

Files are organized as `{workspace_id}/{project_id}/{task_id}/{filename}`. The upload flow: user drops a file on the task detail panel, the client validates size (under 10MB) and type, uploads to Supabase Storage, inserts an attachment record, and other users see the new attachment via their existing real-time subscription.

Image attachments render as inline previews in the task detail view. PDFs and documents show file-type icons. A lightbox opens on click for full-size viewing.

### Step 5: Deploy and Configure for Production

```text
Prepare this Supabase project for production. Set up: environment-specific configs (dev/staging/prod), database migrations workflow using Supabase CLI, proper CORS and redirect URLs, email templates for magic links, and rate limiting on edge functions. Also create a seed script that populates a demo workspace with sample data for new users.
```

Production configuration covers the things that are easy to forget:

- **Environments**: `.env.local` (local dev with `supabase start`), `.env.staging`, `.env.production`
- **Migrations**: `supabase db diff` generates migrations from local changes, `supabase db push` applies them to the linked project. CI runs `supabase db push` on merge to main.
- **CORS**: only the app domain and localhost in dev. No wildcards in production.
- **Redirect URLs**: explicit whitelist for OAuth callbacks.
- **Rate limiting**: 100 requests/minute per IP on edge functions.
- **Email templates**: branded magic link emails that match the app's design.

A seed script creates a "Getting Started" demo workspace with 3 sample projects, 12 tasks across all status columns, and 2 sample comments. It runs on `supabase db reset` and gives new users something to interact with immediately instead of staring at an empty board.

All 14 RLS policies are verified with test queries before deployment -- each one tested with an authorized user, an unauthorized user, and an unauthenticated request.

## Real-World Example

Marta ships the entire backend in 2 days instead of the 6 weeks a custom Node.js API would have taken. Zero servers to maintain. The Supabase free tier handles her first 500 users, and the Pro plan at $25/month covers her to 10,000.

Magic links mean users sign in without passwords -- the conversion rate on signup is higher than she expected. Real-time subscriptions make the Kanban board feel alive: when one user moves a task, everyone sees it move. Presence shows who is currently looking at the board. File attachments with workspace-scoped storage policies mean she never had to write a single line of access control logic for uploads.

She launches the MVP, gets her first 10 paying users within a month, and spends her time building product features instead of maintaining infrastructure. A competitor building a similar tool on a custom backend is still setting up their WebSocket server.
