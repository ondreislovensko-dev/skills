---
title: Build an Auth System with Better Auth
slug: build-auth-system-with-better-auth
description: >-
  Implement authentication for a TypeScript app using Better Auth — email/password
  login, OAuth providers, magic links, two-factor authentication, session
  management, and role-based access control.
skills:
  - better-auth
  - drizzle-orm
  - neon
  - resend
category: development
tags:
  - authentication
  - auth
  - security
  - typescript
  - oauth
---

# Build an Auth System with Better Auth

Hana wants auth for her SaaS that doesn't lock her into a vendor (like Clerk) or require running a separate service (like Keycloak). Better Auth is a TypeScript-native auth library that runs in her existing server — email/password, Google/GitHub OAuth, magic links, 2FA, and RBAC, all with full type safety. No third-party dashboard, no per-user pricing, complete control over user data.

## Step 1: Install and Configure

```bash
npm install better-auth
npx @better-auth/cli generate  # Generate database schema
npx @better-auth/cli migrate    # Apply migrations
```

```typescript
// src/lib/auth.ts
import { betterAuth } from "better-auth";
import { drizzleAdapter } from "better-auth/adapters/drizzle";
import { db } from "./db";
import { twoFactor, magicLink, organization, admin } from "better-auth/plugins";
import { Resend } from "resend";

const resend = new Resend(process.env.RESEND_API_KEY);

export const auth = betterAuth({
  database: drizzleAdapter(db, { provider: "pg" }),
  baseURL: process.env.NEXT_PUBLIC_APP_URL,

  emailAndPassword: {
    enabled: true,
    requireEmailVerification: true,
    minPasswordLength: 10,
  },

  socialProviders: {
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    },
    github: {
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
    },
  },

  plugins: [
    twoFactor({
      issuer: "MyApp",
    }),
    magicLink({
      sendMagicLink: async ({ email, url }) => {
        await resend.emails.send({
          from: "auth@myapp.com",
          to: email,
          subject: "Sign in to MyApp",
          html: `<a href="${url}">Click here to sign in</a>. This link expires in 10 minutes.`,
        });
      },
    }),
    organization(),
    admin(),
  ],

  session: {
    expiresIn: 60 * 60 * 24 * 7, // 7 days
    updateAge: 60 * 60 * 24,      // Refresh daily
    cookieCache: {
      enabled: true,
      maxAge: 60 * 5, // 5 min client-side cache
    },
  },

  emailVerification: {
    sendVerificationEmail: async ({ user, url }) => {
      await resend.emails.send({
        from: "auth@myapp.com",
        to: user.email,
        subject: "Verify your email",
        html: `<a href="${url}">Verify your email</a>`,
      });
    },
  },
});

export type Session = typeof auth.$Infer.Session;
```

## Step 2: API Route Handler

```typescript
// src/app/api/auth/[...all]/route.ts (Next.js App Router)
import { auth } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";

export const { GET, POST } = toNextJsHandler(auth);
```

## Step 3: Client-Side Auth Hook

```typescript
// src/lib/auth-client.ts
import { createAuthClient } from "better-auth/react";
import { twoFactorClient, magicLinkClient, organizationClient } from "better-auth/client/plugins";

export const authClient = createAuthClient({
  baseURL: process.env.NEXT_PUBLIC_APP_URL,
  plugins: [
    twoFactorClient(),
    magicLinkClient(),
    organizationClient(),
  ],
});

export const {
  signIn,
  signUp,
  signOut,
  useSession,
  twoFactor,
  magicLink,
  organization,
} = authClient;
```

## Step 4: Auth UI Components

```tsx
// src/components/LoginForm.tsx
"use client";
import { signIn, signUp, magicLink } from "@/lib/auth-client";
import { useState } from "react";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    const action = mode === "signin" ? signIn.email : signUp.email;
    const { error } = await action({ email, password });
    if (error) setError(error.message);
  };

  return (
    <div className="max-w-sm mx-auto space-y-4">
      <form onSubmit={handleSubmit} className="space-y-3">
        <input
          type="email" value={email} onChange={(e) => setEmail(e.target.value)}
          placeholder="Email" required
          className="w-full px-3 py-2 border rounded"
        />
        <input
          type="password" value={password} onChange={(e) => setPassword(e.target.value)}
          placeholder="Password" required minLength={10}
          className="w-full px-3 py-2 border rounded"
        />
        {error && <p className="text-red-500 text-sm">{error}</p>}
        <button className="w-full py-2 bg-blue-600 text-white rounded">
          {mode === "signin" ? "Sign In" : "Sign Up"}
        </button>
      </form>

      <div className="flex gap-2">
        <button
          onClick={() => signIn.social({ provider: "google" })}
          className="flex-1 py-2 border rounded"
        >
          Google
        </button>
        <button
          onClick={() => signIn.social({ provider: "github" })}
          className="flex-1 py-2 border rounded"
        >
          GitHub
        </button>
      </div>

      <button
        onClick={async () => {
          if (email) await magicLink.sendMagicLink({ email });
        }}
        className="w-full text-sm text-blue-600"
      >
        Send magic link instead
      </button>

      <button
        onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
        className="w-full text-sm text-gray-500"
      >
        {mode === "signin" ? "Need an account? Sign up" : "Already have an account? Sign in"}
      </button>
    </div>
  );
}
```

## Step 5: Protect Routes with Middleware

```typescript
// src/middleware.ts
import { auth } from "@/lib/auth";
import { headers } from "next/headers";

const protectedRoutes = ["/dashboard", "/settings", "/api/protected"];
const adminRoutes = ["/admin"];

export default auth.api.getMiddleware({
  customRedirect: async (session, request) => {
    const path = new URL(request.url).pathname;

    if (protectedRoutes.some((r) => path.startsWith(r)) && !session) {
      return Response.redirect(new URL("/login", request.url));
    }

    if (adminRoutes.some((r) => path.startsWith(r))) {
      if (!session || session.user.role !== "admin") {
        return Response.redirect(new URL("/dashboard", request.url));
      }
    }
  },
});
```

## Summary

Hana has a complete auth system running in her own infrastructure. Email/password with verification, Google and GitHub OAuth, magic links for passwordless login, and TOTP 2FA — all type-safe with full TypeScript inference. No per-user pricing (Clerk costs $0.02/user/month after the free tier), no vendor lock-in, and the user data lives in her own database. The organization plugin adds multi-tenancy (teams, roles, invites), and the admin plugin gives her a way to manage users. Session caching on the client side means the auth check doesn't hit the database on every request.
