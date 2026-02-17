---
name: s3-storage
description: >-
  Manages S3-compatible object storage (AWS S3, MinIO, Cloudflare R2,
  DigitalOcean Spaces, Backblaze B2, Wasabi, Supabase Storage). Use when
  the user wants to create buckets, upload/download files, set up lifecycle
  policies, configure CORS, manage presigned URLs, implement multipart
  uploads, set up replication, handle versioning, configure access policies,
  or build file management features on top of S3-compatible APIs. Trigger
  words: s3, minio, r2, object storage, bucket, presigned url, multipart
  upload, lifecycle policy, s3 cors, storage backend, file storage, blob
  storage, spaces, backblaze, wasabi.
license: Apache-2.0
compatibility: "Node.js 18+ or Python 3.9+. Requires AWS SDK v3 or compatible S3 client library."
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: devops
  tags: ["s3", "object-storage", "minio", "cloud-storage"]
---

# S3 Storage

## Overview

Manages S3-compatible object storage across all major providers. Covers bucket operations, file upload/download patterns, presigned URLs for secure client-side uploads, multipart uploads for large files, lifecycle policies, versioning, replication, access control, CORS configuration, and event notifications. All examples use the AWS SDK v3 which works with any S3-compatible endpoint.

## Instructions

### 1. Client Setup

**AWS S3:**
```javascript
import { S3Client } from '@aws-sdk/client-s3';

const s3 = new S3Client({
  region: 'us-east-1',
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID,
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY,
  },
});
```

**MinIO (self-hosted):**
```javascript
const s3 = new S3Client({
  region: 'us-east-1',
  endpoint: 'http://localhost:9000',
  credentials: {
    accessKeyId: process.env.MINIO_ACCESS_KEY,
    secretAccessKey: process.env.MINIO_SECRET_KEY,
  },
  forcePathStyle: true, // Required for MinIO
});
```

**Cloudflare R2:**
```javascript
const s3 = new S3Client({
  region: 'auto',
  endpoint: `https://${process.env.CF_ACCOUNT_ID}.r2.cloudflarestorage.com`,
  credentials: {
    accessKeyId: process.env.R2_ACCESS_KEY,
    secretAccessKey: process.env.R2_SECRET_KEY,
  },
});
```

**DigitalOcean Spaces:**
```javascript
const s3 = new S3Client({
  region: 'nyc3',
  endpoint: 'https://nyc3.digitaloceanspaces.com',
  credentials: {
    accessKeyId: process.env.DO_SPACES_KEY,
    secretAccessKey: process.env.DO_SPACES_SECRET,
  },
});
```

**Backblaze B2:**
```javascript
const s3 = new S3Client({
  region: 'us-west-004',
  endpoint: 'https://s3.us-west-004.backblazeb2.com',
  credentials: {
    accessKeyId: process.env.B2_KEY_ID,
    secretAccessKey: process.env.B2_APP_KEY,
  },
});
```

**Python (boto3) — works with all providers:**
```python
import boto3

s3 = boto3.client('s3',
    endpoint_url='http://localhost:9000',  # Omit for AWS
    aws_access_key_id=os.environ['ACCESS_KEY'],
    aws_secret_access_key=os.environ['SECRET_KEY'],
)
```

### 2. Bucket Operations

```javascript
import {
  CreateBucketCommand,
  ListBucketsCommand,
  DeleteBucketCommand,
  HeadBucketCommand,
} from '@aws-sdk/client-s3';

// Create bucket
await s3.send(new CreateBucketCommand({ Bucket: 'my-app-uploads' }));

// List buckets
const { Buckets } = await s3.send(new ListBucketsCommand({}));

// Check if bucket exists
try {
  await s3.send(new HeadBucketCommand({ Bucket: 'my-app-uploads' }));
} catch (e) {
  if (e.name === 'NotFound') console.log('Bucket does not exist');
}
```

### 3. File Operations

**Upload:**
```javascript
import { PutObjectCommand } from '@aws-sdk/client-s3';

await s3.send(new PutObjectCommand({
  Bucket: 'my-app-uploads',
  Key: 'users/123/avatar.jpg',
  Body: fileBuffer,
  ContentType: 'image/jpeg',
  Metadata: {
    'uploaded-by': 'user-123',
    'original-name': 'photo.jpg',
  },
}));
```

**Download:**
```javascript
import { GetObjectCommand } from '@aws-sdk/client-s3';

const { Body, ContentType, ContentLength } = await s3.send(
  new GetObjectCommand({ Bucket: 'my-app-uploads', Key: 'users/123/avatar.jpg' })
);
// Body is a readable stream
const chunks = [];
for await (const chunk of Body) chunks.push(chunk);
const buffer = Buffer.concat(chunks);
```

**List objects with pagination:**
```javascript
import { ListObjectsV2Command } from '@aws-sdk/client-s3';

let continuationToken;
const allKeys = [];
do {
  const { Contents, NextContinuationToken, IsTruncated } = await s3.send(
    new ListObjectsV2Command({
      Bucket: 'my-app-uploads',
      Prefix: 'users/123/',
      MaxKeys: 1000,
      ContinuationToken: continuationToken,
    })
  );
  allKeys.push(...(Contents || []).map(obj => obj.Key));
  continuationToken = IsTruncated ? NextContinuationToken : undefined;
} while (continuationToken);
```

**Delete:**
```javascript
import { DeleteObjectCommand, DeleteObjectsCommand } from '@aws-sdk/client-s3';

// Single
await s3.send(new DeleteObjectCommand({ Bucket: 'my-app-uploads', Key: 'old-file.txt' }));

// Bulk (up to 1000 per request)
await s3.send(new DeleteObjectsCommand({
  Bucket: 'my-app-uploads',
  Delete: {
    Objects: keys.map(Key => ({ Key })),
    Quiet: true,
  },
}));
```

**Copy/move:**
```javascript
import { CopyObjectCommand } from '@aws-sdk/client-s3';

// Copy
await s3.send(new CopyObjectCommand({
  Bucket: 'my-app-uploads',
  CopySource: 'my-app-uploads/old/path.jpg',
  Key: 'new/path.jpg',
}));

// Move = copy + delete original
```

### 4. Presigned URLs

Secure client-side uploads/downloads without exposing credentials:

**Upload presigned URL:**
```javascript
import { PutObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

const url = await getSignedUrl(s3, new PutObjectCommand({
  Bucket: 'my-app-uploads',
  Key: `uploads/${userId}/${filename}`,
  ContentType: contentType,
}), { expiresIn: 3600 }); // 1 hour

// Client uploads directly to S3:
// fetch(url, { method: 'PUT', body: file, headers: { 'Content-Type': contentType } })
```

**Download presigned URL:**
```javascript
import { GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

const url = await getSignedUrl(s3, new GetObjectCommand({
  Bucket: 'my-app-uploads',
  Key: 'reports/q4-2024.pdf',
}), { expiresIn: 900 }); // 15 minutes
```

### 5. Multipart Upload (large files)

For files > 100MB:

```javascript
import {
  CreateMultipartUploadCommand,
  UploadPartCommand,
  CompleteMultipartUploadCommand,
  AbortMultipartUploadCommand,
} from '@aws-sdk/client-s3';

const PART_SIZE = 10 * 1024 * 1024; // 10MB per part

async function multipartUpload(bucket, key, buffer) {
  const { UploadId } = await s3.send(new CreateMultipartUploadCommand({
    Bucket: bucket, Key: key,
  }));

  const parts = [];
  try {
    for (let i = 0; i < buffer.length; i += PART_SIZE) {
      const partNumber = Math.floor(i / PART_SIZE) + 1;
      const { ETag } = await s3.send(new UploadPartCommand({
        Bucket: bucket, Key: key, UploadId,
        PartNumber: partNumber,
        Body: buffer.slice(i, i + PART_SIZE),
      }));
      parts.push({ PartNumber: partNumber, ETag });
    }

    await s3.send(new CompleteMultipartUploadCommand({
      Bucket: bucket, Key: key, UploadId,
      MultipartUpload: { Parts: parts },
    }));
  } catch (e) {
    await s3.send(new AbortMultipartUploadCommand({
      Bucket: bucket, Key: key, UploadId,
    }));
    throw e;
  }
}
```

Or use the high-level `@aws-sdk/lib-storage`:
```javascript
import { Upload } from '@aws-sdk/lib-storage';

const upload = new Upload({
  client: s3,
  params: { Bucket: 'my-app-uploads', Key: 'large-file.zip', Body: stream },
  partSize: 10 * 1024 * 1024,
  leavePartsOnError: false,
});
upload.on('httpUploadProgress', (p) => console.log(`${p.loaded}/${p.total}`));
await upload.done();
```

### 6. Bucket Policies and Access Control

**Public read for a prefix (e.g., static assets):**
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadAssets",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::my-app-uploads/public/*"
  }]
}
```

**Block all public access (recommended default):**
```javascript
import { PutPublicAccessBlockCommand } from '@aws-sdk/client-s3';

await s3.send(new PutPublicAccessBlockCommand({
  Bucket: 'my-app-uploads',
  PublicAccessBlockConfiguration: {
    BlockPublicAcls: true,
    IgnorePublicAcls: true,
    BlockPublicPolicy: true,
    RestrictPublicBuckets: true,
  },
}));
```

### 7. Lifecycle Policies

Automate storage cost management:

```javascript
import { PutBucketLifecycleConfigurationCommand } from '@aws-sdk/client-s3';

await s3.send(new PutBucketLifecycleConfigurationCommand({
  Bucket: 'my-app-uploads',
  LifecycleConfiguration: {
    Rules: [
      {
        ID: 'delete-temp-after-1-day',
        Prefix: 'tmp/',
        Status: 'Enabled',
        Expiration: { Days: 1 },
      },
      {
        ID: 'archive-old-logs',
        Prefix: 'logs/',
        Status: 'Enabled',
        Transitions: [
          { Days: 30, StorageClass: 'STANDARD_IA' },
          { Days: 90, StorageClass: 'GLACIER' },
        ],
        Expiration: { Days: 365 },
      },
      {
        ID: 'cleanup-incomplete-uploads',
        Prefix: '',
        Status: 'Enabled',
        AbortIncompleteMultipartUpload: { DaysAfterInitiation: 7 },
      },
    ],
  },
}));
```

### 8. Versioning

```javascript
import {
  PutBucketVersioningCommand,
  ListObjectVersionsCommand,
} from '@aws-sdk/client-s3';

// Enable
await s3.send(new PutBucketVersioningCommand({
  Bucket: 'my-app-uploads',
  VersioningConfiguration: { Status: 'Enabled' },
}));

// List versions of a file
const { Versions } = await s3.send(new ListObjectVersionsCommand({
  Bucket: 'my-app-uploads',
  Prefix: 'config/settings.json',
}));

// Get specific version
await s3.send(new GetObjectCommand({
  Bucket: 'my-app-uploads',
  Key: 'config/settings.json',
  VersionId: 'abc123',
}));
```

### 9. CORS Configuration

Required for browser-based uploads:

```javascript
import { PutBucketCorsCommand } from '@aws-sdk/client-s3';

await s3.send(new PutBucketCorsCommand({
  Bucket: 'my-app-uploads',
  CORSConfiguration: {
    CORSRules: [{
      AllowedHeaders: ['*'],
      AllowedMethods: ['GET', 'PUT', 'POST', 'HEAD'],
      AllowedOrigins: ['https://myapp.com', 'http://localhost:3000'],
      ExposeHeaders: ['ETag', 'x-amz-meta-*'],
      MaxAgeSeconds: 3600,
    }],
  },
}));
```

### 10. Event Notifications

Trigger actions when objects are created/deleted:

**AWS S3 → Lambda/SQS/SNS:**
```javascript
import { PutBucketNotificationConfigurationCommand } from '@aws-sdk/client-s3';

await s3.send(new PutBucketNotificationConfigurationCommand({
  Bucket: 'my-app-uploads',
  NotificationConfiguration: {
    LambdaFunctionConfigurations: [{
      LambdaFunctionArn: 'arn:aws:lambda:us-east-1:123:function:process-upload',
      Events: ['s3:ObjectCreated:*'],
      Filter: {
        Key: { FilterRules: [{ Name: 'prefix', Value: 'uploads/' }] },
      },
    }],
  },
}));
```

**MinIO → Webhook:**
```bash
mc event add myminio/my-bucket arn:minio:sqs::1:webhook \
  --event put --prefix uploads/
```

## Examples

### Example 1: User Avatar Upload System

**Input:** "Build a secure avatar upload system. Users get a presigned URL from our API, upload directly to S3 from the browser, then we resize the image to 3 sizes (small, medium, large) and serve them through CloudFront."

**Output:**
- API endpoint generating presigned PUT URLs with content-type validation (images only)
- CORS config allowing browser uploads from the app domain
- S3 event notification triggering a Lambda that resizes to 64x64, 256x256, 512x512
- CloudFront distribution with `/avatars/*` path pointing to the processed images bucket
- Cleanup lifecycle rule deleting original uploads after processing

### Example 2: Self-Hosted MinIO for Development

**Input:** "Set up MinIO as a local S3 replacement for development. Configure it with Docker Compose, create the same buckets and policies we use in production, and write a helper module that switches between MinIO locally and real S3 in production based on an environment variable."

**Output:**
- Docker Compose with MinIO service, persistent volume, and health check
- Init script creating buckets, setting policies, and uploading seed data
- Storage module with `createStorageClient()` that returns an S3Client configured for MinIO or AWS based on `STORAGE_PROVIDER` env var
- Wrapper functions for common operations (upload, download, presign, delete) with consistent error handling
- Integration tests that run against local MinIO in CI

## Guidelines

- Always use `forcePathStyle: true` for MinIO and self-hosted S3-compatible stores
- Use presigned URLs for client-side uploads — never proxy large files through your API server
- Set lifecycle rules on every bucket — at minimum, abort incomplete multipart uploads after 7 days
- Block public access by default, whitelist only when necessary
- Use object key prefixes for logical organization (`users/{id}/`, `uploads/{date}/`)
- Never put user input directly in object keys — sanitize and validate filenames
- Set `ContentType` explicitly on upload — S3 defaults to `application/octet-stream`
- Use `ContentDisposition: 'attachment; filename="name.pdf"'` for downloadable files
- For high throughput: use S3 Transfer Acceleration or distribute keys across prefixes
- Monitor costs: S3 GET/PUT requests cost money — batch operations where possible
- Always handle the `NoSuchKey` error gracefully on downloads
- Use bucket versioning for critical data (configs, user documents), not for ephemeral files
- R2 has no egress fees — consider it for CDN-heavy workloads
- MinIO is fully S3-compatible — use it for local development and testing
