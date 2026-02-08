---
name: blender-vse-pipeline
description: >-
  Automate video editing in Blender's Video Sequence Editor with Python. Use
  when the user wants to add video, image, or audio strips, create transitions,
  apply effects, build edit timelines, batch assemble footage, estimate render
  times, or script any VSE workflow from the command line.
license: Apache-2.0
compatibility: >-
  Requires Blender 3.0+. FFmpeg codecs included with Blender.
  Run: blender --background --python script.py
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: automation
  tags: ["blender", "video-editing", "vse", "timeline", "pipeline"]
---

# Blender VSE Pipeline

## Overview

Automate video editing with Blender's Video Sequence Editor (VSE) using Python. Add and arrange strips (video, image, audio), create transitions, apply effects, assemble edits from file lists, and render final video — all headlessly from the terminal.

## Instructions

### 1. Initialize the sequence editor

```python
import bpy

scene = bpy.context.scene

# Ensure the sequence editor exists
if not scene.sequence_editor:
    scene.sequence_editor_create()

seq_editor = scene.sequence_editor
sequences = seq_editor.sequences

# Set timeline range
scene.frame_start = 1
scene.frame_end = 250
scene.render.fps = 24
```

### 2. Add video strips

```python
import bpy

sequences = bpy.context.scene.sequence_editor.sequences

# Add a movie strip
# sequences.new_movie(name, filepath, channel, frame_start)
strip = sequences.new_movie(
    name="Clip_A",
    filepath="/path/to/video.mp4",
    channel=1,
    frame_start=1
)

# Strip properties
print(f"Duration: {strip.frame_final_duration} frames")
print(f"Start: {strip.frame_final_start}")
print(f"End: {strip.frame_final_end}")

# Trim the strip (set in/out points)
strip.frame_offset_start = 24    # skip first second
strip.frame_offset_end = 48      # trim last 2 seconds

# Set volume for embedded audio
strip.volume = 0.8

# Move strip on timeline
strip.frame_start = 100
strip.channel = 2
```

### 3. Add image and image sequence strips

```python
import bpy
import glob

sequences = bpy.context.scene.sequence_editor.sequences

# Single image (hold for a duration)
img_strip = sequences.new_image(
    name="Title_Card",
    filepath="/path/to/title.png",
    channel=2,
    frame_start=1,
    fit_method='FIT'    # FIT, FILL, STRETCH, ORIGINAL
)
img_strip.frame_final_duration = 72  # hold for 3 seconds at 24fps

# Image sequence
img_files = sorted(glob.glob("/path/to/frames/frame_*.png"))
img_seq = sequences.new_image(
    name="Render_Sequence",
    filepath=img_files[0],
    channel=1,
    frame_start=1
)
# Add remaining images to the strip
for f in img_files[1:]:
    img_seq.elements.append(f.split("/")[-1])
```

### 4. Add audio strips

```python
import bpy

sequences = bpy.context.scene.sequence_editor.sequences

# Add a sound strip
audio = sequences.new_sound(
    name="Music",
    filepath="/path/to/music.mp3",
    channel=3,
    frame_start=1
)

audio.volume = 0.6
audio.pitch = 1.0
audio.pan = 0.0       # -1.0 left, 0.0 center, 1.0 right

# Fade audio in/out using animation
audio.volume = 0.0
audio.keyframe_insert(data_path="volume", frame=1)
audio.volume = 0.6
audio.keyframe_insert(data_path="volume", frame=24)
audio.volume = 0.6
audio.keyframe_insert(data_path="volume", frame=audio.frame_final_end - 48)
audio.volume = 0.0
audio.keyframe_insert(data_path="volume", frame=audio.frame_final_end)
```

### 5. Add transitions and effects

```python
import bpy

sequences = bpy.context.scene.sequence_editor.sequences

# Prerequisite: two strips that overlap in time
clip_a = sequences["Clip_A"]
clip_b = sequences["Clip_B"]

# Cross dissolve between two strips
cross = sequences.new_effect(
    name="CrossDissolve",
    type='CROSS',        # CROSS, GAMMA_CROSS, ADD, SUBTRACT, MULTIPLY, ALPHA_OVER, WIPE
    channel=3,
    frame_start=clip_a.frame_final_end - 24,
    frame_end=clip_b.frame_final_start + 24,
    seq1=clip_a,
    seq2=clip_b
)

# Color strip (solid color background)
color = sequences.new_effect(
    name="BlackBG",
    type='COLOR',
    channel=1,
    frame_start=1,
    frame_end=48
)
color.color = (0, 0, 0)

# Text strip
text = sequences.new_effect(
    name="Title",
    type='TEXT',
    channel=4,
    frame_start=1,
    frame_end=72
)
text.text = "My Video Title"
text.font_size = 80
text.color = (1, 1, 1, 1)
text.location = (0.5, 0.5)           # normalized position
text.align_x = 'CENTER'
text.align_y = 'CENTER'
text.use_shadow = True
text.shadow_color = (0, 0, 0, 0.8)

# Speed control
speed = sequences.new_effect(
    name="SlowMo",
    type='SPEED',
    channel=5,
    frame_start=clip_a.frame_final_start,
    frame_end=clip_a.frame_final_end,
    seq1=clip_a
)
speed.speed_factor = 0.5  # half speed

# Transform (position, scale, rotation)
transform = sequences.new_effect(
    name="Transform",
    type='TRANSFORM',
    channel=5,
    frame_start=1,
    frame_end=100,
    seq1=clip_a
)
transform.scale_start_x = 1.2
transform.scale_start_y = 1.2
transform.translate_start_x = 50
```

### 6. Strip modifiers for color correction

```python
import bpy

strip = bpy.context.scene.sequence_editor.sequences["Clip_A"]

# Brightness/Contrast modifier
bc = strip.modifiers.new(name="BrightContrast", type='BRIGHT_CONTRAST')
bc.bright = 0.1
bc.contrast = 0.15

# Color Balance modifier
cb = strip.modifiers.new(name="ColorBalance", type='COLOR_BALANCE')
cb.color_balance.lift = (0.95, 0.95, 1.0)
cb.color_balance.gamma = (1.0, 1.0, 1.0)
cb.color_balance.gain = (1.1, 1.05, 0.95)

# Hue Correct modifier
hue = strip.modifiers.new(name="HueCorrect", type='HUE_CORRECT')

# Curves modifier
curves = strip.modifiers.new(name="Curves", type='CURVES')

# White Balance modifier
wb = strip.modifiers.new(name="WhiteBalance", type='WHITE_BALANCE')
wb.white_value = (0.95, 0.95, 1.0)
```

### 7. Render the final video

```python
import bpy

scene = bpy.context.scene

# Set output to video
scene.render.filepath = "/tmp/final_edit.mp4"
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.constant_rate_factor = 'MEDIUM'
scene.render.ffmpeg.audio_codec = 'AAC'
scene.render.ffmpeg.audio_bitrate = 192

# Resolution
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080
scene.render.resolution_percentage = 100

# Auto-set frame range to match content
all_strips = scene.sequence_editor.sequences_all
if all_strips:
    scene.frame_start = min(s.frame_final_start for s in all_strips)
    scene.frame_end = max(s.frame_final_end for s in all_strips)

bpy.ops.render.render(animation=True)
print(f"Rendered to: {scene.render.filepath}")
```

### 8. Estimate render times from strip data

```python
import bpy
import time

scene = bpy.context.scene
seq = scene.sequence_editor

# Analyze strip durations per channel
channel_data = {}
for strip in seq.sequences_all:
    ch = strip.channel
    dur = strip.frame_final_duration
    channel_data.setdefault(ch, []).append({
        'name': strip.name,
        'type': strip.type,
        'start': strip.frame_final_start,
        'end': strip.frame_final_end,
        'duration': dur,
    })

total_frames = scene.frame_end - scene.frame_start + 1
fps = scene.render.fps

print(f"=== VSE Render Estimate ===")
print(f"Total frames: {total_frames}")
print(f"Duration: {total_frames / fps:.1f} seconds")
print(f"FPS: {fps}")

for ch in sorted(channel_data.keys()):
    print(f"\nChannel {ch}:")
    for s in channel_data[ch]:
        print(f"  {s['name']} ({s['type']}): frames {s['start']}-{s['end']} ({s['duration']} frames)")

# Benchmark render time with a single frame
start_time = time.time()
scene.render.filepath = "/tmp/_benchmark"
scene.frame_set(scene.frame_start)
bpy.ops.render.render(write_still=True)
frame_time = time.time() - start_time

estimated_total = frame_time * total_frames
print(f"\nSingle frame render: {frame_time:.2f}s")
print(f"Estimated total: {estimated_total / 3600:.1f} hours")
```

## Examples

### Example 1: Assemble an edit from a shot list

**User request:** "Build a timeline from a list of video clips with crossfades between them"

```python
import bpy
import os

clips = [
    "/path/to/shot_01.mp4",
    "/path/to/shot_02.mp4",
    "/path/to/shot_03.mp4",
    "/path/to/shot_04.mp4",
]
crossfade_frames = 12  # half-second at 24fps

scene = bpy.context.scene
scene.render.fps = 24
if not scene.sequence_editor:
    scene.sequence_editor_create()

sequences = scene.sequence_editor.sequences
current_frame = 1

prev_strip = None
for i, clip_path in enumerate(clips):
    name = os.path.splitext(os.path.basename(clip_path))[0]

    if prev_strip and crossfade_frames > 0:
        current_frame -= crossfade_frames

    strip = sequences.new_movie(
        name=name,
        filepath=clip_path,
        channel=1 + (i % 2),  # alternate channels for crossfades
        frame_start=current_frame
    )

    if prev_strip and crossfade_frames > 0:
        cross = sequences.new_effect(
            name=f"Fade_{i}",
            type='GAMMA_CROSS',
            channel=3,
            frame_start=current_frame,
            frame_end=current_frame + crossfade_frames,
            seq1=prev_strip,
            seq2=strip
        )

    current_frame += strip.frame_final_duration
    prev_strip = strip

scene.frame_start = 1
scene.frame_end = current_frame

scene.render.filepath = "/tmp/assembled_edit.mp4"
scene.render.image_settings.file_format = 'FFMPEG'
scene.render.ffmpeg.format = 'MPEG4'
scene.render.ffmpeg.codec = 'H264'
scene.render.ffmpeg.audio_codec = 'AAC'
scene.render.resolution_x = 1920
scene.render.resolution_y = 1080

bpy.ops.render.render(animation=True)
print("Edit assembled and rendered.")
```

### Example 2: Batch add text overlays from CSV

**User request:** "Add text titles at specific timecodes from a CSV file"

```python
import bpy
import csv

scene = bpy.context.scene
scene.render.fps = 24
if not scene.sequence_editor:
    scene.sequence_editor_create()

sequences = scene.sequence_editor.sequences

# CSV format: text,start_seconds,duration_seconds
csv_data = [
    ("Introduction", 0, 3),
    ("Chapter 1: Getting Started", 15, 4),
    ("Chapter 2: Advanced Topics", 120, 4),
    ("Conclusion", 300, 5),
]

fps = scene.render.fps
for text_content, start_sec, dur_sec in csv_data:
    start_frame = int(start_sec * fps) + 1
    end_frame = start_frame + int(dur_sec * fps)

    text = sequences.new_effect(
        name=text_content[:20],
        type='TEXT',
        channel=5,
        frame_start=start_frame,
        frame_end=end_frame
    )
    text.text = text_content
    text.font_size = 60
    text.color = (1, 1, 1, 1)
    text.location = (0.5, 0.15)
    text.align_x = 'CENTER'
    text.use_shadow = True
    text.shadow_color = (0, 0, 0, 0.7)

    print(f"Added: '{text_content}' at {start_sec}s for {dur_sec}s")

bpy.ops.wm.save_as_mainfile(filepath="/tmp/titled_edit.blend")
```

## Guidelines

- Always call `scene.sequence_editor_create()` if `scene.sequence_editor` is `None` — it doesn't exist by default.
- Use `sequences.new_movie()`, `new_image()`, `new_sound()`, and `new_effect()` to add strips. Avoid `bpy.ops.sequencer.*` operators in background mode — they require a specific editor context.
- Cross dissolves need two strips on different channels that overlap in time. Place clips on alternating channels (1, 2, 1, 2…) when building crossfade timelines.
- `frame_offset_start` and `frame_offset_end` trim content without moving the strip. `frame_start` moves the strip on the timeline.
- Render as image sequence first for long edits, then assemble with ffmpeg. This allows resuming after crashes.
- For audio fade in/out, insert keyframes on `strip.volume` — the VSE has no built-in audio fade effect.
- Strip modifiers (Color Balance, Curves, etc.) apply per-strip color correction without separate effect strips.
- Set `scene.render.resolution_x/y` to match your source footage resolution to avoid scaling artifacts.
- Use `sequences_all` to iterate all strips including meta-strip children. Use `sequences` for top-level strips only.
- The VSE processes channels bottom-to-top — higher channel numbers are layered on top.
