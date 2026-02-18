---
name: twitter-x-marketing
description: >-
  Create, optimize, and automate content for Twitter/X including tweets, threads,
  Spaces, and API automation. Use when someone asks to "write a tweet", "create a
  Twitter thread", "grow on X", "Twitter API integration", "automate tweeting",
  "Twitter analytics", "Twitter bot", or "X content strategy". Covers platform-specific
  formatting, X API v2 integration, thread creation, analytics, and growth tactics.
license: Apache-2.0
compatibility: "X API v2 (Free, Basic, Pro tiers). Node.js/Python examples."
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: marketing
  tags: ["twitter", "x", "social-media", "threads", "api", "content-marketing"]
---

# Twitter/X Marketing

## Overview

This skill helps AI agents create high-performing Twitter/X content and integrate with the X API. It covers tweet formatting, thread writing, API-based publishing and analytics, bot creation, and growth strategies tailored to X's real-time, conversation-driven algorithm.

## Instructions

### Platform Rules & Algorithm

X algorithm priorities (2025-2026):

- **Replies and conversations** — reply chains weight 5-10x more than likes
- **Time spent on tweet** — longer reads (threads) get boosted
- **Media engagement** — images get 1.5-2x more engagement than text-only
- **Bookmarks** — strong signal (people save what's genuinely useful)
- **Follower engagement rate** — high engagement from followers = more distribution to non-followers
- **Recency** — X is real-time, posts decay fast (peak: first 30-60 min)

What kills reach:
- External links in tweet body (30-50% reach penalty — put in reply)
- Excessive hashtags (2 max, 0 is often better)
- Engagement bait ("RT if you agree")
- Posting and disappearing (no replies to your own tweet)
- Cross-posting from other platforms with watermarks

### Content Formats

#### Single Tweet (280 characters)
```
[Hook — sharp, opinionated, or surprising]

[Optional: 1-2 supporting lines]

[Optional: CTA or question]
```

**Formatting rules:**
- 280 character limit (threads for longer content)
- Line breaks work and improve readability
- No markdown rendering — use CAPS or emoji for emphasis
- 1-2 hashtags max (or none — they look spammy now)
- Mentions: tag people only when relevant to them
- Images: 1200x675px (16:9) for single, 1200x1200px for multi

#### Threads (Highest reach potential)
```
Tweet 1/🧵: [Strong hook — this determines if anyone reads the rest]

Tweet 2: [Context or problem statement]

Tweet 3-7: [Main content — one point per tweet, clear and punchy]

Tweet 8: [Summary or key takeaway]

Tweet 9: [CTA — follow for more, bookmark this, share your experience]

Tweet 10: [Self-reply with link if needed]
```

**Thread rules:**
- First tweet is EVERYTHING — it appears alone in the feed
- 7-12 tweets optimal (enough value, not exhausting)
- Each tweet should stand alone AND flow as a sequence
- Number tweets for scanability (1/, 2/, etc. or use 🧵)
- End with CTA: "Follow @handle for more [topic]"
- Reply to your own thread with links, resources, promo

#### Polls
- 2-4 options, 24h duration is optimal
- Controversial or surprising options drive votes
- Follow up with results analysis tweet

#### Spaces (Live Audio)
- Schedule in advance for promotion
- 30-60 minutes optimal
- Record and clip highlights for posts
- Pin a tweet with agenda before starting

#### Video
- Native upload (not YouTube links)
- Under 2:20 minutes for feed (60-90s optimal)
- Square (1:1) or vertical (9:16) — NOT widescreen
- Captions required (auto-generated available)
- Hook in first 2 seconds

### X API v2 Integration

#### Authentication
```typescript
// X API uses OAuth 2.0 with PKCE for user context
// or OAuth 1.0a for user-context legacy
// or Bearer token for app-only context

// App-only (read-only, no user context)
const BEARER_TOKEN = process.env.X_BEARER_TOKEN;

// OAuth 2.0 User Context (for posting)
import { Client, auth } from 'twitter-api-sdk';

const authClient = new auth.OAuth2User({
  client_id: process.env.X_CLIENT_ID,
  client_secret: process.env.X_CLIENT_SECRET,
  callback: process.env.X_CALLBACK_URL,
  scopes: ['tweet.read', 'tweet.write', 'users.read', 'offline.access'],
});

// Get authorization URL
const authUrl = authClient.generateAuthURL({
  state: 'random-state',
  code_challenge_method: 'S256',
});

// Exchange code for token
const { token } = await authClient.requestAccessToken(code);
```

#### Post Tweets
```typescript
const client = new Client(authClient);

// Simple tweet
const { data } = await client.tweets.createTweet({
  text: 'Hello from the API!',
});

// Tweet with image
// Step 1: Upload media (uses v1.1 endpoint)
const mediaUploadRes = await fetch('https://upload.twitter.com/1.1/media/upload.json', {
  method: 'POST',
  headers: {
    Authorization: `OAuth ...`, // OAuth 1.0a signature required for media upload
  },
  body: formData, // multipart/form-data with media_data (base64)
});
const { media_id_string } = await mediaUploadRes.json();

// Step 2: Create tweet with media
await client.tweets.createTweet({
  text: 'Tweet with image',
  media: { media_ids: [media_id_string] },
});

// Tweet with poll
await client.tweets.createTweet({
  text: 'Which do you prefer?',
  poll: {
    options: ['Option A', 'Option B', 'Option C'],
    duration_minutes: 1440, // 24 hours
  },
});

// Reply to a tweet
await client.tweets.createTweet({
  text: 'This is a reply',
  reply: { in_reply_to_tweet_id: '1234567890' },
});

// Quote tweet
await client.tweets.createTweet({
  text: 'Great insight here 👇',
  quote_tweet_id: '1234567890',
});
```

#### Create Thread
```typescript
async function postThread(tweets: string[]) {
  let previousTweetId: string | undefined;

  for (const text of tweets) {
    const params: any = { text };
    if (previousTweetId) {
      params.reply = { in_reply_to_tweet_id: previousTweetId };
    }

    const { data } = await client.tweets.createTweet(params);
    previousTweetId = data.id;

    // Rate limit: wait between tweets
    await new Promise(r => setTimeout(r, 1000));
  }

  return previousTweetId; // Last tweet ID
}

await postThread([
  '🧵 Thread: 5 things I learned building a SaaS in 2025\n\nAfter 12 months, $40K MRR, and countless mistakes — here are the real lessons:',
  '1/ Your first 100 users don\'t come from marketing.\n\nThey come from manually reaching out to people who have the problem you solve.\n\nDMs, forums, communities. One by one.',
  '2/ Ship weekly, not monthly.\n\nEvery week without shipping is a week without learning.\n\nOur best feature came from a bug report on a half-baked release.',
  // ... more tweets
  'If this was useful, follow @handle for weekly threads on building SaaS.\n\nBookmark 🔖 this thread to reference later.',
]);
```

#### Analytics
```typescript
// Get tweet metrics (requires tweet.read scope)
const { data } = await client.tweets.findTweetById('1234567890', {
  'tweet.fields': ['public_metrics', 'organic_metrics', 'created_at'],
});

console.log(data.public_metrics);
// { retweet_count, reply_count, like_count, quote_count, bookmark_count, impression_count }

// Get user metrics
const { data: user } = await client.users.findMyUser({
  'user.fields': ['public_metrics'],
});
// { followers_count, following_count, tweet_count, listed_count }

// Search recent tweets (for monitoring)
const { data: tweets } = await client.tweets.tweetsRecentSearch({
  query: '"your brand" OR @yourbrand -is:retweet',
  max_results: 100,
  'tweet.fields': ['public_metrics', 'created_at', 'author_id'],
});
```

### API Tiers & Limits

| Tier | Price | Tweets/month | Read | Features |
|------|-------|-------------|------|----------|
| Free | $0 | 1,500 write | 10K read | Post, delete, basic lookup |
| Basic | $100/mo | 3,000 write | 10K read | + search, user lookup |
| Pro | $5,000/mo | 300K write | 1M read | + full archive, analytics |

### Growth Strategy

**Posting schedule:** 3-5 tweets/day + 1-2 threads/week

**Content mix:**
- 30% threads (deep value — get bookmarked and shared)
- 25% single tweets (opinions, hot takes, observations)
- 20% replies to big accounts (free distribution to their audience)
- 15% engagement (polls, questions, "unpopular opinion:")
- 10% retweets with commentary (curating = authority)

**Best posting times:** 8-10 AM and 5-7 PM target timezone (weekdays)

**Reply strategy:**
- Reply to large accounts in your niche within first 30 min of their post
- Add genuine insight (not "great post 🔥")
- Your reply is seen by THEIR audience — it's free reach
- Reply to your own tweets to extend visibility (algorithm treats as conversation)

**What works in 2025-2026:**
- Contrarian takes with nuance ("Unpopular: React is becoming legacy")
- Before/after stories with specifics
- Lists with practical value ("10 tools that replaced my entire stack")
- Screenshots of results/dashboards (social proof)
- Quote-tweeting trending topics with your perspective

## Best Practices

- Links in reply to self, not in main tweet (reach penalty is real)
- 0-2 hashtags maximum — they're mostly dead on X
- Post first tweet of a thread at peak time, rest follows immediately
- Engage with replies on your tweets for 30 min after posting — signals to algorithm
- Bookmark > Like in algorithm weight — create content worth saving
- Vertical video outperforms horizontal on mobile (70%+ mobile users)
- Use alt text on images — accessibility + SEO + extra indexable text
- Thread first tweet must stand alone — most people only see it in feed
- Repost your best threads after 3-4 months with "In case you missed it:"
