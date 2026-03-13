---
title: Build an Image Optimization Pipeline with Sharp
slug: build-image-optimization-pipeline-with-sharp
description: >-
  Build a high-performance image processing pipeline using Sharp — resize,
  convert to modern formats, generate responsive srcsets, optimize for
  Core Web Vitals, and serve through a CDN.
skills:
  - sharp
  - aws-s3
  - aws-cloudfront
  - docker-compose
category: media
tags:
  - images
  - optimization
  - performance
  - core-web-vitals
  - cdn
---

# Build an Image Optimization Pipeline with Sharp

Diego runs an e-commerce site with 50,000 product images. Pages load slowly because images are unoptimized PNGs at original resolution. His Core Web Vitals are terrible — LCP is 6 seconds on mobile. He needs to convert everything to modern formats (WebP/AVIF), generate multiple sizes for responsive loading, and serve them through a CDN. The pipeline should process existing images in bulk and handle new uploads automatically.

## Step 1: Image Processing Service

```typescript
// src/services/image-processor.ts
import sharp from "sharp";
import { PutObjectCommand, S3Client } from "@aws-sdk/client-s3";

const s3 = new S3Client({ region: process.env.AWS_REGION });

interface ProcessingResult {
  variants: ImageVariant[];
  metadata: ImageMetadata;
  blurhash: string;
}

interface ImageVariant {
  width: number;
  format: "webp" | "avif" | "jpeg";
  key: string;
  size: number;
}

const SIZES = [
  { width: 320, suffix: "sm" },
  { width: 640, suffix: "md" },
  { width: 960, suffix: "lg" },
  { width: 1280, suffix: "xl" },
  { width: 1920, suffix: "2xl" },
];

const FORMATS = ["webp", "avif", "jpeg"] as const;

export async function processImage(
  inputBuffer: Buffer,
  basePath: string
): Promise<ProcessingResult> {
  const image = sharp(inputBuffer);
  const metadata = await image.metadata();

  const variants: ImageVariant[] = [];

  for (const size of SIZES) {
    // Skip sizes larger than original
    if (size.width > (metadata.width || 0)) continue;

    for (const format of FORMATS) {
      const pipeline = sharp(inputBuffer)
        .resize(size.width, null, {
          withoutEnlargement: true,
          fit: "inside",
        });

      let processed: Buffer;
      switch (format) {
        case "webp":
          processed = await pipeline.webp({ quality: 80, effort: 4 }).toBuffer();
          break;
        case "avif":
          processed = await pipeline.avif({ quality: 65, effort: 4 }).toBuffer();
          break;
        case "jpeg":
          processed = await pipeline.jpeg({ quality: 80, progressive: true, mozjpeg: true }).toBuffer();
          break;
      }

      const key = `${basePath}/${size.suffix}.${format}`;
      await s3.send(new PutObjectCommand({
        Bucket: process.env.S3_BUCKET!,
        Key: key,
        Body: processed,
        ContentType: `image/${format}`,
        CacheControl: "public, max-age=31536000, immutable",
      }));

      variants.push({ width: size.width, format, key, size: processed.length });
    }
  }

  // Generate tiny placeholder for blur-up loading
  const placeholder = await sharp(inputBuffer)
    .resize(20)
    .webp({ quality: 20 })
    .toBuffer();
  const blurhash = `data:image/webp;base64,${placeholder.toString("base64")}`;

  return {
    variants,
    metadata: {
      width: metadata.width!,
      height: metadata.height!,
      format: metadata.format!,
      originalSize: inputBuffer.length,
    },
    blurhash,
  };
}
```

## Step 2: Bulk Processing Script

```typescript
// scripts/bulk-optimize.ts
import { S3Client, ListObjectsV2Command, GetObjectCommand } from "@aws-sdk/client-s3";
import { processImage } from "../src/services/image-processor";
import pLimit from "p-limit";

const s3 = new S3Client({ region: process.env.AWS_REGION });
const limit = pLimit(5); // Process 5 images concurrently

async function bulkOptimize() {
  let continuationToken: string | undefined;
  let processed = 0;
  let skipped = 0;

  do {
    const response = await s3.send(new ListObjectsV2Command({
      Bucket: process.env.S3_BUCKET!,
      Prefix: "products/originals/",
      ContinuationToken: continuationToken,
    }));

    const tasks = (response.Contents || [])
      .filter((obj) => /\.(jpg|jpeg|png|webp)$/i.test(obj.Key || ""))
      .map((obj) => limit(async () => {
        const id = obj.Key!.split("/").pop()!.replace(/\.[^.]+$/, "");
        const outputPath = `products/optimized/${id}`;

        try {
          const data = await s3.send(new GetObjectCommand({
            Bucket: process.env.S3_BUCKET!,
            Key: obj.Key!,
          }));
          const buffer = Buffer.from(await data.Body!.transformToByteArray());
          const result = await processImage(buffer, outputPath);

          const savings = (1 - result.variants.reduce((sum, v) => sum + v.size, 0) /
            (result.metadata.originalSize * result.variants.length)) * 100;

          console.log(`✅ ${id}: ${result.variants.length} variants, ${savings.toFixed(0)}% smaller`);
          processed++;
        } catch (err) {
          console.error(`❌ ${id}: ${err}`);
        }
      }));

    await Promise.all(tasks);
    continuationToken = response.NextContinuationToken;
  } while (continuationToken);

  console.log(`\nDone: ${processed} processed, ${skipped} skipped`);
}

bulkOptimize();
```

## Step 3: Responsive Image Component

```tsx
// src/components/OptimizedImage.tsx
interface Props {
  basePath: string;
  alt: string;
  width: number;
  height: number;
  blurhash: string;
  priority?: boolean;
  sizes?: string;
}

const CDN = process.env.NEXT_PUBLIC_CDN_URL;

export function OptimizedImage({ basePath, alt, width, height, blurhash, priority, sizes = "100vw" }: Props) {
  return (
    <picture>
      {/* AVIF — smallest, best quality, limited browser support */}
      <source
        type="image/avif"
        srcSet={`${CDN}/${basePath}/sm.avif 320w, ${CDN}/${basePath}/md.avif 640w, ${CDN}/${basePath}/lg.avif 960w, ${CDN}/${basePath}/xl.avif 1280w`}
        sizes={sizes}
      />
      {/* WebP — good compression, wide support */}
      <source
        type="image/webp"
        srcSet={`${CDN}/${basePath}/sm.webp 320w, ${CDN}/${basePath}/md.webp 640w, ${CDN}/${basePath}/lg.webp 960w, ${CDN}/${basePath}/xl.webp 1280w`}
        sizes={sizes}
      />
      {/* JPEG fallback */}
      <img
        src={`${CDN}/${basePath}/lg.jpeg`}
        srcSet={`${CDN}/${basePath}/sm.jpeg 320w, ${CDN}/${basePath}/md.jpeg 640w, ${CDN}/${basePath}/lg.jpeg 960w, ${CDN}/${basePath}/xl.jpeg 1280w`}
        sizes={sizes}
        alt={alt}
        width={width}
        height={height}
        loading={priority ? "eager" : "lazy"}
        decoding={priority ? "sync" : "async"}
        style={{ backgroundImage: `url(${blurhash})`, backgroundSize: "cover" }}
      />
    </picture>
  );
}
```

## Summary

Diego's LCP dropped from 6 seconds to 1.8 seconds. The pipeline processes each product image into 15 variants (5 sizes × 3 formats), with the browser automatically picking the best format and size. AVIF saves ~50% over JPEG, WebP ~30%. The blurhash placeholder eliminates layout shift. Bulk processing handled 50,000 existing images in a few hours, and new uploads get processed automatically. Total image storage grew 3×, but bandwidth dropped 65% thanks to smaller served files and aggressive CDN caching.
