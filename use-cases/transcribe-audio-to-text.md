---
title: "Transcribe Audio to Text with Whisper"
slug: transcribe-audio-to-text
description: "Convert speech to text from MP3, WAV, M4A files using OpenAI Whisper in the terminal."
skill: voice-to-text
category: productivity
tags: [audio, transcription, whisper, speech-to-text, voice]
---

# Transcribe Audio to Text with Whisper

## The Problem

You have meeting recordings, voice memos, podcast episodes, or interview audio files that need to be converted to text. Manual transcription takes 4-6x the audio duration — a 1-hour meeting means 4-6 hours of typing. Online transcription services raise privacy concerns for sensitive content like legal depositions, medical notes, or internal strategy discussions. And at $1-2 per minute, transcribing a backlog of recordings gets expensive fast.

You need a fast, scriptable, self-hosted solution that works from the command line and keeps sensitive audio off third-party servers.

## The Solution

Use the **voice-to-text** skill to transcribe any audio file using OpenAI Whisper. It works with local Whisper (free, completely offline) or the OpenAI API (fast, cloud-based). Supports MP3, WAV, M4A, FLAC, and 50+ other formats including video files where the audio track is extracted automatically.

## Step-by-Step Walkthrough

### Step 1: Point at Your Audio File

The simplest case — one file, one command:

```text
Transcribe meeting-recording.mp3 to text
```

That's it. The skill handles everything from here: detecting the best transcription method for your setup, converting audio formats if needed, selecting the right model size, and producing clean text output.

### Step 2: The Right Approach Is Selected Automatically

Based on the file size, available system resources, and whether an OpenAI API key is configured, the skill picks the optimal path:

- **Local Whisper** for privacy-sensitive content or offline use. Runs entirely on your machine — nothing leaves the network. Requires Python and a few GB of disk space for the model. With a GPU, it's fast. Without one, it's slower but still works.
- **OpenAI API** for speed when cloud processing is acceptable. Faster than real-time transcription, no GPU needed locally, and the accuracy is excellent.

For a 45-minute meeting recording, local Whisper with the `small` model finishes in about 8 minutes on a modern laptop with a GPU, or roughly 25 minutes on CPU only. The API version returns in under 2 minutes regardless of your hardware.

The decision comes down to one question: can this audio leave your machine? If yes, the API is faster. If no — internal meetings, legal recordings, medical dictation — local Whisper keeps everything private.

### Step 3: Audio Is Processed

Format conversion happens transparently via FFmpeg. Whisper expects specific input formats, but the skill handles the conversion automatically. Hand it an MP4 video from Zoom, a WMA recording from an old dictaphone, a FLAC file from a professional mic, or a voice memo in M4A from an iPhone — it just works. The audio track is extracted from video files automatically.

For long files, progress is displayed so you know it hasn't stalled. Files over 2 hours are automatically chunked into segments to prevent memory issues, with overlapping boundaries to avoid cutting words in half.

### Step 4: Clean Text Output

The transcription lands as a clean text file:

- **Duration:** 45:32
- **Words:** 6,847
- **Output:** `meeting-recording.txt`

The text is formatted with paragraph breaks at natural pauses. Punctuation and capitalization are applied automatically — this isn't raw speech-to-text output full of run-on sentences. Speaker changes aren't labeled by default (that requires diarization, a separate processing step), but sentence boundaries are detected reliably.

For subtitle output, the skill generates properly formatted SRT or VTT files with timestamps for each caption segment. Timestamps are aligned to sentence boundaries rather than arbitrary time intervals, which makes the subtitles far more readable.

### Step 5: Follow Up with Analysis

This is where transcription becomes genuinely useful. The raw text file is just the starting point — the real value comes from what you do with it:

```text
Summarize the meeting and extract action items from meeting-recording.txt
```

The transcript gets analyzed and structured: a concise summary of what was discussed, decisions that were made, and a list of action items with assignees and deadlines pulled from the conversation context.

Other common follow-ups:

```text
Find all mentions of "Q3 budget" or "hiring plan" in the transcript
```

```text
Create a structured outline from this interview for a blog post
```

The transcript is plain text, which means any text-processing tool or AI agent can work with it. Search it, summarize it, extract quotes, build outlines — the audio is no longer locked in a format that only humans can process by listening in real time.

## Real-World Example

Priya is a product manager who records weekly standups on Zoom. Each 30-minute standup generates discussion, decisions, and action items that she used to manually type up afterward — 45 minutes of note-taking for every 30-minute meeting. That's 3 hours a month spent on what should be automatic.

Now the workflow takes two minutes of her time. After the meeting:

```text
Transcribe standup-2026-02-17.mp4 and extract action items
```

The recording is transcribed in 5 minutes while she works on something else. Action items are pulled out automatically:

- **@john:** Fix login bug by Friday
- **@sarah:** Send design specs to engineering by Wednesday
- **@mike:** Schedule customer interview for next week

She pastes the action items into the team's project tracker and moves on. The full transcript is archived in case anyone needs to check what was actually said about a specific topic.

A podcaster on her team uses the same skill for a completely different workflow — generating SRT subtitles for accessibility compliance:

```text
Create subtitles for episode-42.mp3 in SRT format
```

The output is a properly formatted `episode-42.srt` with timestamps aligned to sentence boundaries, ready to upload to YouTube or embed in a podcast player. What used to require either expensive transcription services or hours of manual timing work now takes a single command.

A third team member, a journalist, has 3 hours of interview recordings from a field assignment:

```text
Transcribe interview-part1.wav interview-part2.wav interview-part3.wav
Then find all mentions of "budget" or "funding"
```

All three files are batch-processed and searched. Every relevant quote surfaces with context, instead of the journalist scrubbing through 3 hours of audio trying to find the moment where the interviewee mentioned the funding round.

## Whisper Model Options

Choosing the right model size is a trade-off between speed and accuracy:

| Model | Speed | Accuracy | RAM Required |
|-------|-------|----------|--------------|
| tiny | ~32x realtime | Good for clear audio | 1GB |
| base | ~16x realtime | Better, handles some noise | 1GB |
| small | ~6x realtime | Great balance of speed and quality | 2GB |
| medium | ~2x realtime | Excellent, handles accents well | 5GB |
| large | ~1x realtime | Best available accuracy | 10GB |

Start with `small` for most use cases — it handles standard meeting audio, podcasts, and clear voice memos with high accuracy. Move to `medium` if you're dealing with heavy accents, significant background noise, or domain-specific vocabulary (medical, legal, technical). The `large` model is worth the extra time for content where every word matters: legal proceedings, medical dictation, or interviews that will be quoted directly in publication.

## Supported Formats

- **Audio:** MP3, WAV, M4A, FLAC, OGG, WMA, AAC
- **Video:** MP4, MOV, AVI, MKV, WEBM (audio track extracted automatically)
- **Other:** Anything FFmpeg can decode

## Tips for Best Results

1. **Clear audio matters most** — a $20 lavalier mic beats a conference room speakerphone every time. The model can't transcribe what it can't hear.
2. **Specify the language** if you know it — skipping auto-detection saves processing time and improves accuracy, especially for non-English content.
3. **Split files over 2 hours** — very long files benefit from chunking to avoid memory pressure and allow progress tracking.
4. **Single-speaker audio** transcribes best — multi-speaker content works but won't label who said what without a separate diarization step.
5. **Normalize audio levels** before transcription if the recording has widely varying volume — quiet passages get worse accuracy.
