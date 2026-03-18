---
title: "Implement a File Upload and Processing Pipeline"
slug: implement-file-upload-pipeline
description: "Build a production file upload system with validation, image/video processing, cloud storage, and async job handling."
skills: [file-upload-processor, media-transcoder, batch-processor]
category: development
tags: [file-upload, image-processing, video, cloud-storage, pipeline]
---

# Implement a File Upload and Processing Pipeline

## The Problem

Every SaaS app eventually needs file uploads -- profile avatars, document attachments, video content. But a naive implementation breaks fast: large files time out the request, unvalidated uploads become a security hole, images need resizing into multiple formats, videos need transcoding, and the whole thing needs to work without blocking the web server.

The typical progression looks like this: start with `multer` saving to disk, hit the first 413 error when someone uploads a 200 MB video, add a size limit, then discover that the disk fills up because nobody cleans up temp files. Move to cloud storage, realize images need thumbnails, bolt on Sharp, discover that synchronous processing blocks the API for 8 seconds per upload. Add a queue, discover that failed jobs disappear silently. Each fix introduces a new problem. Building this pipeline from scratch takes a week of fiddling with streams, queues, and cloud storage APIs.

## The Solution

Using the **file-upload-processor**, **media-transcoder**, and **batch-processor** skills, the agent builds a complete pipeline from upload to processed output: a validated upload endpoint that streams directly to S3, an image processing pipeline that generates thumbnails and optimized variants, a video transcoder that normalizes formats and tracks progress, and a BullMQ job queue that orchestrates it all asynchronously.

## Step-by-Step Walkthrough

### Step 1: Build the Upload Endpoint with Validation

```text
I have a Node.js/Express API. I need a file upload endpoint that handles images
(jpg, png, webp up to 10MB), videos (mp4, webm up to 500MB), and documents
(pdf up to 25MB). Upload to S3-compatible storage. Include validation for file
type, size, and basic malware scanning via magic bytes.
```

The upload flow never touches the local disk. Multipart form data streams directly to S3 while the server validates file type by reading magic bytes -- not just file extensions, which are trivially spoofed. A JPEG must start with `FF D8 FF`, a PNG with `89 50 4E 47`, a WebP with `52 49 46 46`. Anything that doesn't match gets rejected before a single byte hits storage.

This matters for security: renaming `malware.exe` to `photo.jpg` would bypass extension-based validation but fails magic byte detection immediately. The validator reads only the first 8 bytes of the stream, so it adds negligible overhead.

Four files do the heavy lifting:

- **upload/routes.ts** -- POST `/api/files/upload` with multer streaming to S3
- **upload/validators.ts** -- magic byte detection, content-type verification, and per-type size limits
- **upload/storage.ts** -- S3 client with presigned URL generation for direct browser uploads
- **upload/models/file.ts** -- file record tracking id, userId, S3 key, processing status, and metadata

The upload flow:

1. Client sends multipart form data
2. Server reads magic bytes from the stream and validates against the allowlist
3. Validated stream pipes directly to S3 (no temp file on disk)
4. Database record created with status `uploaded`
5. Processing job dispatched to the appropriate queue
6. Client receives file ID and status URL immediately

The response returns in under 200ms regardless of file size because the heavy work happens asynchronously. The client can either poll the status endpoint (`GET /api/files/:id/status`) for progress updates, or register a webhook URL when creating the upload to receive a POST notification when processing completes.

For the frontend, a React hook wraps the entire flow:

```typescript
const { upload, progress, status, variants } = useFileUpload();
// progress: 0-100 for upload, then "processing", then "complete"
// variants: null until processed, then { thumb, medium, original }
```

### Step 2: Add Image Processing with Sharp

```text
When an image is uploaded, generate these variants:
- thumbnail: 150x150, cropped to center, webp, quality 80
- medium: max 800px wide, preserve aspect ratio, webp, quality 85
- original: strip EXIF GPS data but keep orientation, convert to webp

Run this asynchronously after upload. Update the file record with variant URLs.
```

Every uploaded image goes through a seven-step pipeline:

1. Download original from S3 to a temp buffer
2. Strip GPS from EXIF metadata (users don't realize their photos contain their home address), auto-rotate based on orientation tag (phones store rotation as metadata, not in the pixel data)
3. Generate thumbnail -- 150x150 cover crop, WebP at quality 80
4. Generate medium -- 800px wide, aspect ratio preserved, WebP at quality 85
5. Convert original to WebP, strip all remaining EXIF, re-upload
6. Upload all three variants to S3 under `files/{id}/thumb.webp`, `medium.webp`, `original.webp`
7. Update database: status changes to `processed`, variants field populated with CDN-ready URLs
8. Clean up the temp buffer (critical -- without this, memory usage climbs with each processed image)

Processing time is roughly 2 seconds for a 5MB JPEG on a 2-core server. The image processor lives in `processing/image.processor.ts`, built on Sharp, with a corresponding BullMQ job handler in `processing/jobs/process-image.job.ts`.

Why WebP for all variants? It's 25-35% smaller than JPEG at equivalent visual quality, supported by every modern browser, and Sharp handles the conversion natively without additional dependencies. The quality settings (80 for thumbnails, 85 for medium) are tuned for the sweet spot where file size drops significantly but visual artifacts aren't noticeable.

### Step 3: Add Video Transcoding with FFmpeg

```text
For video uploads, transcode to H.264/AAC MP4 at 720p and generate a
thumbnail from the 2-second mark. Videos over 100MB should use multipart
upload to S3. Show progress via webhook or polling endpoint.
```

Video is where the pipeline earns its keep. Raw uploads from users come in every format imaginable -- MOV from iPhones, AVI from screen recorders, MKV from professional tools. The transcoder normalizes everything to H.264 main profile with AAC audio at 128k, capped at 720p with CRF 23. This ensures consistent playback across all browsers without requiring the client to handle codec detection. A thumbnail gets extracted as a PNG at the 2-second mark (not the first frame, which is often black) and resized to 400px wide.

The video processor starts by probing the source file with `ffprobe` to extract duration, resolution, codec, and bitrate -- this metadata goes into the database record even before transcoding starts, so the UI can show video duration and resolution immediately.

For large files, the upload strategy changes entirely. Instead of streaming through the API server (which would tie up a connection for minutes), the client gets presigned multipart upload URLs and uploads 5MB chunks directly to S3 in parallel. The server just completes the multipart upload and queues the processing job.

The status endpoint at `GET /api/files/:id/status` returns real-time progress, updated throughout the transcode:

```json
{
  "id": "file_abc",
  "status": "processing",
  "progress": 65,
  "variants": null
}
```

### Step 4: Set Up the Job Queue

```text
Set up BullMQ with Redis for the processing jobs. Image jobs should have
concurrency 5, video jobs concurrency 2 (CPU-heavy). Add retry with backoff,
dead letter queue for failed jobs, and cleanup of temp files.
```

Two separate BullMQ queues keep image and video processing from competing for resources:

| Queue | Concurrency | Retries | Timeout | Backoff |
|-------|-------------|---------|---------|---------|
| `image-processing` | 5 | 3 | 5 min | Exponential |
| `video-processing` | 2 | 2 | 30 min | Exponential |

Failed jobs move to a dead letter queue after exhausting retries -- no silent failures, no lost uploads. A cron job purges completed jobs after 7 days. Temp files in `/tmp/processing/` get cleaned up after each job completes, whether it succeeded or failed.

The queue survives server restarts because Redis persists the job state. If a worker crashes mid-transcode, the job retries automatically on the next available worker. The separation of concerns is important: the API server accepts uploads and returns immediately, while workers on separate processes (or separate machines) handle the CPU-intensive processing. Scaling workers independently of the API server means upload throughput and processing throughput scale separately.

A monitoring dashboard tracks queue depth, processing times, and failure rates. When the video queue depth exceeds 20 jobs, an alert fires -- that's the signal to scale up video workers or investigate a processing bottleneck.

## Real-World Example

Marcus is building a learning platform where instructors upload course videos and slide decks, and students submit assignment PDFs. The current setup saves everything to the local disk at `/uploads`, which broke the moment they deployed to a second server behind a load balancer -- uploads land on one server, downloads route to the other, and students see broken video links half the time.

The immediate problem is the load balancer, but the real problem is deeper: there's no validation (a student uploaded a .exe renamed to .pdf last week), no image resizing (course cover images are 8 MB phone photos served at full resolution), and videos play in some browsers but not others because instructors upload in every format from MOV to AVI.

He describes his stack (Next.js API routes, PostgreSQL, S3-compatible storage via Backblaze B2) and the three file types he needs to handle. The agent builds the full pipeline in stages: first the upload endpoint with streaming to S3 and magic-byte validation (rejecting the .exe-disguised-as-pdf problem immediately), then Sharp-based image processing that turns 8 MB phone photos into 150 KB WebP thumbnails, and finally FFmpeg transcoding that normalizes instructor videos from whatever format they arrive in to 720p H.264 for consistent playback across all browsers.

The multipart upload support for large videos is the feature instructors appreciate most -- instead of a 500 MB upload timing out after 10 minutes, it uploads in parallel 5 MB chunks with resume capability. If the connection drops at 80%, only the remaining chunks need to re-upload.

The real test comes during course prep week, when 50 instructors upload simultaneously. The BullMQ queue handles the burst gracefully -- image jobs process in seconds, video jobs queue up and work through at a steady pace, and every instructor sees real-time progress on their uploads.

What would have taken two weeks of piecing together Stack Overflow answers is running in production in two days. The platform handles 200+ uploads daily with no files lost, no timeouts, and no blocked API requests. Storage costs are predictable because Backblaze B2 charges $5/TB/month with free egress -- a fraction of what AWS S3 would cost for the same workload, and the S3-compatible API means switching providers later requires changing one environment variable.
