---
name: youtube-marketing
description: >-
  Create, optimize, and manage YouTube content for channel growth, audience building,
  and monetization. Use when someone asks to "grow on YouTube", "optimize YouTube videos",
  "YouTube SEO", "YouTube Shorts strategy", "YouTube API integration", "automate YouTube
  uploads", "YouTube analytics", "YouTube thumbnail", or "YouTube content strategy".
  Covers long-form video, Shorts, SEO, thumbnail design, YouTube Data API, analytics,
  monetization, and growth strategies.
license: Apache-2.0
compatibility: "YouTube Data API v3, YouTube Analytics API. Requires Google Cloud project with YouTube API enabled."
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: marketing
  tags: ["youtube", "video", "social-media", "seo", "shorts", "marketing", "api", "monetization"]
---

# YouTube Marketing

## Overview

This skill helps AI agents create high-performing YouTube content and integrate with the YouTube Data API. It covers long-form video strategy, Shorts, SEO optimization, thumbnail design, upload automation, analytics, monetization paths, and growth strategies for YouTube's search-and-recommendation algorithm.

## Instructions

### Platform Rules & Algorithm

YouTube has two discovery systems:

**Search (YouTube is the #2 search engine):**
- Title, description, tags — keyword matching
- Video transcript/captions — YouTube indexes spoken words
- Engagement rate — CTR and watch time after click
- Video age — fresh content gets a boost for trending queries

**Recommendations (Browse/Suggested — 70%+ of views):**
- Click-through rate (CTR) — thumbnail + title get the click
- Average view duration (AVD) — how much of the video people watch
- Session time — does your video lead to more YouTube watching?
- Viewer satisfaction — likes, comments, shares, "not interested" rate
- Upload consistency — channels with regular schedules get preferred

What kills reach:
- Clickbait that doesn't deliver (high CTR + low AVD = algorithm death)
- Long intros before value (viewers leave in first 30 seconds)
- Inconsistent upload schedule
- Wrong audience signals (video attracts wrong viewers → low AVD)
- Misleading thumbnails (high bounce rate)

### Content Formats

#### Long-Form Video (8-20 minutes — core of YouTube)

**Structure:**
```
0:00-0:30  — Hook (promise value, show result, create curiosity)
0:30-1:00  — Context (what this video covers, why it matters)
1:00-X:00  — Main content (deliver on the hook, organized sections)
Last 30s   — CTA (subscribe, next video, comment prompt)
```

**Production specs:**
- Resolution: 1920x1080 (1080p) minimum, 3840x2160 (4K) preferred
- Frame rate: 24fps (cinematic), 30fps (standard), 60fps (gaming/action)
- Audio: clear voice, -14 to -12 LUFS loudness, minimal background noise
- Format: MP4, H.264 codec, AAC audio
- Max file size: 256GB or 12 hours (whichever is less)

**Retention techniques:**
- Pattern interrupts every 30-60 seconds (B-roll, zoom, angle change, graphic)
- Open loops ("I'll show you the results in a minute, but first...")
- Chapters/timestamps in description (viewers jump to sections, counts as engagement)
- Visual variety — never same shot for more than 30 seconds

#### YouTube Shorts (Under 60 seconds — vertical)

**Specs:**
- Aspect ratio: 9:16 (1080x1920px)
- Duration: 15-60 seconds (under 30s for highest completion)
- No end screens or cards supported
- Music from YouTube's library available
- Can be clipped from long-form (with #Shorts in title)

**Shorts strategy:**
- Hook in first 1 second (text + visual)
- Single focused idea per Short
- Loop-friendly (ending connects to beginning for replays)
- Use as funnel to long-form ("full tutorial on my channel")
- 3-5 Shorts/week alongside long-form content

**What works for Shorts:**
- Quick tips/tutorials (3-step process)
- Satisfying before/after
- Hot takes / controversial opinions
- Clips from long-form with context overlay
- Trending audio + niche topic

#### Community Posts
- Available after 500 subscribers
- Polls, images, text posts, video teasers
- Good for engagement between uploads
- Poll results inform future content topics
- Post 2-3x/week between video uploads

#### Live Streams
- Sends notifications to subscribers
- Super Chats for monetization
- Premiere feature: scheduled first-watch with live chat
- Good for Q&A, tutorials, announcements
- Archive becomes regular video (gets recommended)

### YouTube SEO

#### Title Optimization
```
Formula: [Primary Keyword] — [Benefit/Hook] ([Modifier])

Good:
  "Next.js Authentication — Complete Guide (2026)"
  "I Built a SaaS in 7 Days — Here's What Happened"
  "5 Python Libraries That Will Save You Hours"

Bad:
  "My New Video About Coding"
  "Part 47 of My Tutorial Series"
  "INSANE!! YOU WON'T BELIEVE THIS!!!"
```

**Title rules:**
- 60-70 characters max (truncates in search/suggestions)
- Primary keyword near the beginning
- Number + benefit works ("5 Tools That...", "How to X in 10 Minutes")
- Capitalize first letter of each major word
- Avoid ALL CAPS (except one emphasis word)
- Test with YouTube search autocomplete — use what people search

#### Description Optimization
```
First 2 lines (shown before "Show more"):
  [Primary keyword sentence. Summarize video value in 1-2 lines.]

Timestamps/Chapters:
  0:00 Introduction
  1:23 Step 1: Setup
  3:45 Step 2: Configuration
  ...

Full description (150-300 words):
  [Detailed summary with natural keyword usage]
  [Related topics and context]
  [Links to resources mentioned]

Links:
  🔗 Resources mentioned: [URLs]
  📧 Newsletter: [URL]
  🐦 Twitter: [URL]

Tags/Keywords (natural, not stuffed):
  Related keywords and phrases woven into text
```

**Description rules:**
- First 150 characters appear in search — front-load keywords
- Timestamps create chapters (minimum 3, at least 10 seconds each)
- 150-300 words total for SEO value
- Include 2-3 related keywords naturally
- Links below the fold (after "Show more")
- Don't keyword-stuff — YouTube can penalize

#### Tags
- 5-15 tags per video
- Primary keyword as first tag
- Mix: exact match, variations, broader terms
- Include common misspellings
- Tags are less important than title/description in 2025-2026 but still help

#### Thumbnail Design
```
Dimensions: 1280x720px (16:9), under 2MB
Format: JPG, PNG, GIF

Design principles:
- High contrast — must be readable at small sizes (mobile)
- Face with emotion — expressive faces get clicks (shock, curiosity, excitement)
- Large text — 3-5 words max, bold, with outline/shadow for readability
- Complementary colors to YouTube's red/white interface
- Consistent branding across videos (recognizable style)
- Rule of thirds — face on one side, text on other

What NOT to do:
- Small text nobody can read on mobile
- Cluttered/busy design
- Misleading imagery
- Exact same thumbnail for every video
- Dark/muddy colors that blend into background
```

#### Closed Captions / Subtitles
- Upload accurate SRT file (auto-captions have errors)
- YouTube indexes caption text for search
- Expands audience to non-native speakers and deaf/HoH
- Multi-language subtitles expand global reach
- Captions improve watch time (people follow along)

### YouTube Data API v3

#### Authentication
```typescript
// YouTube uses Google OAuth 2.0
import { google } from 'googleapis';

const oauth2Client = new google.auth.OAuth2(
  process.env.GOOGLE_CLIENT_ID,
  process.env.GOOGLE_CLIENT_SECRET,
  process.env.GOOGLE_REDIRECT_URI
);

// Generate auth URL
const authUrl = oauth2Client.generateAuthUrl({
  access_type: 'offline', // Gets refresh token
  scope: [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube',
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/yt-analytics.readonly',
  ],
});

// Exchange code for tokens
const { tokens } = await oauth2Client.getToken(code);
oauth2Client.setCredentials(tokens);

const youtube = google.youtube({ version: 'v3', auth: oauth2Client });
```

#### Upload Video
```typescript
import fs from 'fs';

const res = await youtube.videos.insert({
  part: ['snippet', 'status', 'contentDetails'],
  requestBody: {
    snippet: {
      title: 'Next.js Authentication — Complete Guide (2026)',
      description: 'Learn how to implement authentication in Next.js...\n\n0:00 Introduction\n1:23 Setup\n...',
      tags: ['nextjs', 'authentication', 'tutorial', 'web development'],
      categoryId: '28', // Science & Technology
      defaultLanguage: 'en',
    },
    status: {
      privacyStatus: 'private', // Upload as private first, review, then publish
      publishAt: '2026-03-01T15:00:00.000Z', // Schedule (must be private)
      selfDeclaredMadeForKids: false,
      license: 'youtube', // or 'creativeCommon'
    },
  },
  media: {
    body: fs.createReadStream('/path/to/video.mp4'),
  },
});

const videoId = res.data.id;
console.log(`Uploaded: https://youtube.com/watch?v=${videoId}`);

// Set thumbnail
await youtube.thumbnails.set({
  videoId,
  media: {
    body: fs.createReadStream('/path/to/thumbnail.jpg'),
  },
});
```

#### Upload Shorts
```typescript
// Shorts are regular videos with #Shorts in title and vertical aspect ratio
await youtube.videos.insert({
  part: ['snippet', 'status'],
  requestBody: {
    snippet: {
      title: '3 Git Commands You Didn\'t Know #Shorts',
      description: 'Quick tips for git productivity.\n\n#Shorts #git #programming',
      tags: ['shorts', 'git', 'programming', 'tips'],
      categoryId: '28',
    },
    status: {
      privacyStatus: 'public',
      selfDeclaredMadeForKids: false,
    },
  },
  media: {
    body: fs.createReadStream('/path/to/short-vertical.mp4'), // 9:16 aspect ratio
  },
});
```

#### Manage Playlists
```typescript
// Create playlist
const playlist = await youtube.playlists.insert({
  part: ['snippet', 'status'],
  requestBody: {
    snippet: {
      title: 'Next.js Complete Course',
      description: 'Full Next.js tutorial series from beginner to advanced.',
    },
    status: { privacyStatus: 'public' },
  },
});

// Add video to playlist
await youtube.playlistItems.insert({
  part: ['snippet'],
  requestBody: {
    snippet: {
      playlistId: playlist.data.id,
      resourceId: { kind: 'youtube#video', videoId: 'abc123' },
      position: 0,
    },
  },
});
```

#### Analytics
```typescript
const youtubeAnalytics = google.youtubeAnalytics({ version: 'v2', auth: oauth2Client });

// Channel analytics
const channelStats = await youtubeAnalytics.reports.query({
  ids: 'channel==MINE',
  startDate: '2026-01-01',
  endDate: '2026-02-18',
  metrics: 'views,estimatedMinutesWatched,averageViewDuration,subscribersGained,likes',
  dimensions: 'day',
  sort: '-day',
});

// Video performance
const videoStats = await youtubeAnalytics.reports.query({
  ids: 'channel==MINE',
  startDate: '2026-01-01',
  endDate: '2026-02-18',
  metrics: 'views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained',
  filters: `video==${videoId}`,
  dimensions: 'day',
});

// Traffic sources
const trafficSources = await youtubeAnalytics.reports.query({
  ids: 'channel==MINE',
  startDate: '2026-01-01',
  endDate: '2026-02-18',
  metrics: 'views,estimatedMinutesWatched',
  dimensions: 'insightTrafficSourceType',
  sort: '-views',
});

// Top videos
const topVideos = await youtubeAnalytics.reports.query({
  ids: 'channel==MINE',
  startDate: '2026-01-01',
  endDate: '2026-02-18',
  metrics: 'views,estimatedMinutesWatched,averageViewDuration,likes,subscribersGained',
  dimensions: 'video',
  sort: '-views',
  maxResults: 20,
});

// Search terms driving traffic (YouTube search)
const searchTerms = await youtube.search.list({
  part: ['snippet'],
  forMine: true,
  type: ['video'],
  maxResults: 50,
});
```

### Monetization

#### YouTube Partner Program (YPP)
Requirements:
- 1,000 subscribers
- 4,000 public watch hours (last 12 months) OR 10M Shorts views (last 90 days)
- Follow YouTube monetization policies
- Have AdSense account linked

Revenue streams:
- **Ad revenue** — $3-8 CPM typical for tech niche
- **Channel memberships** — monthly recurring from subscribers ($4.99-49.99/mo)
- **Super Chat / Super Stickers** — live stream donations
- **Super Thanks** — one-time tips on videos
- **YouTube Shopping** — link products directly
- **Shorts revenue** — share of Shorts feed ad revenue (lower RPM than long-form)

#### Beyond YPP
- **Sponsorships** — $50-200 per 1,000 views for tech niche (direct deals)
- **Affiliate links** — Amazon Associates, tool referral programs
- **Own products** — courses, templates, SaaS (highest margin)
- **Consulting/services** — YouTube as lead generation
- **Patreon/membership sites** — exclusive content for paying subscribers

### Growth Strategy

**Upload schedule:** 1-2 long-form videos/week + 3-5 Shorts/week

**Content mix:**
- 50% long-form tutorials/educational (search traffic + watch time)
- 25% Shorts (new audience discovery)
- 15% trend-jacking / commentary (riding trending topics)
- 10% community engagement (polls, Q&A, behind-the-scenes)

**First 48 hours are critical:**
- Share to all social platforms immediately
- Reply to EVERY comment (engagement signals)
- Pin a comment with a question to drive discussion
- Post to relevant communities (Reddit, Discord, forums)
- Send to email list if you have one

**Playlist strategy:**
- Group related videos into playlists
- Playlist auto-play increases session time
- Series playlists show "Next episode" overlay
- Optimize playlist titles for search keywords

**Collaboration:**
- Collaborate with channels of similar size
- Guest appearances expand both audiences
- "Collab" videos get boosted by algorithm (both audiences engage)

**Shorts → Long-form funnel:**
- Create Shorts that tease long-form content
- "Full tutorial on my channel" CTA
- Pin long-form video link in Shorts comments
- Shorts bring subscribers who then watch long-form

## Best Practices

- Thumbnail + title are 80% of the click decision — spend time on them
- First 30 seconds determine if people stay — hook immediately, no long intros
- Upload as unlisted → set thumbnail → add end screen → then publish (avoid algorithm seeing low CTR on default thumbnail)
- Chapters in description improve retention (viewers jump to relevant parts instead of leaving)
- Cards and end screens — always point to your best-performing video or a relevant playlist
- Upload SRT captions — auto-captions have errors, YouTube indexes caption text for search
- Consistency beats virality — 1 video/week for 2 years > random posting hoping for a hit
- Shorts and long-form serve different purposes: Shorts for reach, long-form for watch time and monetization
- Study your Analytics → Audience tab → "When your viewers are on YouTube" to find optimal posting times
- Every video should answer: "Why should someone click THIS video instead of the other 10 on this topic?"
