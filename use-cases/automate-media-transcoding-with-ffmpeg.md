---
title: Automate Media Transcoding with FFmpeg
slug: automate-media-transcoding-with-ffmpeg
description: >-
  Build an automated media processing pipeline with FFmpeg — transcode videos
  for web delivery, generate thumbnails, extract audio, create HLS streams,
  and add watermarks at scale.
skills:
  - ffmpeg
  - sharp
  - inngest
  - aws-s3
  - docker-compose
category: media
tags:
  - video
  - transcoding
  - ffmpeg
  - media-processing
  - automation
---

# Automate Media Transcoding with FFmpeg

Tomás runs a course platform where instructors upload raw video lectures — 4K MOV files, screen recordings in MKV, phone videos in various formats. Students complain about buffering, mobile playback fails, and storage costs are ballooning. He needs an automated pipeline that takes any uploaded video and produces web-optimized formats: HLS for adaptive streaming, MP4 fallback, thumbnails, and extracted audio for podcast feeds.

## Step 1: Video Analysis and Validation

```bash
#!/bin/bash
# scripts/analyze-video.sh — Get video metadata as JSON
INPUT="$1"

ffprobe -v quiet -print_format json -show_format -show_streams "$INPUT" | jq '{
  duration: (.format.duration | tonumber | round),
  size_mb: ((.format.size | tonumber) / 1048576 | round),
  video: (.streams[] | select(.codec_type=="video") | {
    codec: .codec_name,
    width: .width,
    height: .height,
    fps: (.r_frame_rate | split("/") | (.[0] | tonumber) / (.[1] | tonumber) | round),
    bitrate_kbps: ((.bit_rate // "0") | tonumber / 1000 | round)
  }),
  audio: (.streams[] | select(.codec_type=="audio") | {
    codec: .codec_name,
    channels: .channels,
    sample_rate: .sample_rate
  })
}'
```

## Step 2: Multi-Quality Transcoding

```bash
#!/bin/bash
# scripts/transcode.sh — Produce multiple quality levels
INPUT="$1"
OUTPUT_DIR="$2"
BASENAME=$(basename "$INPUT" | sed 's/\.[^.]*$//')

mkdir -p "$OUTPUT_DIR"

# 1080p — High quality
ffmpeg -i "$INPUT" \
  -c:v libx264 -preset medium -crf 23 \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" \
  -c:a aac -b:a 128k -ac 2 \
  -movflags +faststart \
  -y "$OUTPUT_DIR/${BASENAME}_1080p.mp4"

# 720p — Standard
ffmpeg -i "$INPUT" \
  -c:v libx264 -preset medium -crf 25 \
  -vf "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2" \
  -c:a aac -b:a 96k -ac 2 \
  -movflags +faststart \
  -y "$OUTPUT_DIR/${BASENAME}_720p.mp4"

# 480p — Mobile / slow connections
ffmpeg -i "$INPUT" \
  -c:v libx264 -preset medium -crf 28 \
  -vf "scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2" \
  -c:a aac -b:a 64k -ac 1 \
  -movflags +faststart \
  -y "$OUTPUT_DIR/${BASENAME}_480p.mp4"

echo "Transcoding complete: $OUTPUT_DIR"
```

## Step 3: Generate HLS Adaptive Streaming

```bash
#!/bin/bash
# scripts/create-hls.sh — Adaptive bitrate streaming
INPUT="$1"
OUTPUT_DIR="$2/hls"

mkdir -p "$OUTPUT_DIR"

ffmpeg -i "$INPUT" \
  -filter_complex "[0:v]split=3[v1][v2][v3]; \
    [v1]scale=1920:1080[v1out]; \
    [v2]scale=1280:720[v2out]; \
    [v3]scale=854:480[v3out]" \
  -map "[v1out]" -c:v:0 libx264 -b:v:0 5000k -maxrate:v:0 5350k -bufsize:v:0 7500k \
  -map "[v2out]" -c:v:1 libx264 -b:v:1 2800k -maxrate:v:1 2996k -bufsize:v:1 4200k \
  -map "[v3out]" -c:v:2 libx264 -b:v:2 1400k -maxrate:v:2 1498k -bufsize:v:2 2100k \
  -map a:0 -c:a aac -b:a 128k -ac 2 \
  -map a:0 -c:a aac -b:a 96k -ac 2 \
  -map a:0 -c:a aac -b:a 64k -ac 1 \
  -f hls \
  -hls_time 6 \
  -hls_playlist_type vod \
  -hls_flags independent_segments \
  -hls_segment_type mpegts \
  -hls_segment_filename "$OUTPUT_DIR/stream_%v/segment_%03d.ts" \
  -master_pl_name master.m3u8 \
  -var_stream_map "v:0,a:0 v:1,a:1 v:2,a:2" \
  "$OUTPUT_DIR/stream_%v/playlist.m3u8"
```

## Step 4: Thumbnails and Audio Extraction

```bash
#!/bin/bash
# scripts/extract-assets.sh
INPUT="$1"
OUTPUT_DIR="$2"

# Generate thumbnail grid (3x3 from evenly spaced frames)
DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$INPUT" | cut -d. -f1)
INTERVAL=$((DURATION / 10))

ffmpeg -i "$INPUT" \
  -vf "fps=1/${INTERVAL},scale=320:180,tile=3x3" \
  -frames:v 1 \
  -y "$OUTPUT_DIR/thumbnail_grid.jpg"

# Single poster thumbnail at 10% mark
POSTER_TIME=$((DURATION / 10))
ffmpeg -i "$INPUT" \
  -ss "$POSTER_TIME" -frames:v 1 \
  -vf "scale=1280:720:force_original_aspect_ratio=decrease" \
  -y "$OUTPUT_DIR/poster.jpg"

# Extract audio as MP3 for podcast feed
ffmpeg -i "$INPUT" \
  -vn -c:a libmp3lame -q:a 4 \
  -y "$OUTPUT_DIR/audio.mp3"
```

## Step 5: Add Watermark

```bash
#!/bin/bash
# scripts/watermark.sh — Burn in a logo watermark
INPUT="$1"
WATERMARK="assets/logo.png"  # Transparent PNG
OUTPUT="$2"

ffmpeg -i "$INPUT" -i "$WATERMARK" \
  -filter_complex "[1:v]scale=120:-1,format=rgba,colorchannelmixer=aa=0.3[wm]; \
    [0:v][wm]overlay=W-w-20:H-h-20" \
  -c:a copy \
  -y "$OUTPUT"
```

## Summary

Tomás now has a pipeline that automatically processes any uploaded video: validates the input, transcodes to three quality levels, generates HLS for adaptive streaming, extracts thumbnails and audio, and optionally adds watermarks. Students get smooth playback on any device, storage costs dropped 60% from optimized encoding, and instructors just upload — the pipeline handles the rest. All built on FFmpeg scripts that can run in Docker, triggered by Inngest when a file upload event fires.
