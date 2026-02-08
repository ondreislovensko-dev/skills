---
name: blender-motion-capture
description: >-
  Automate motion capture and tracking workflows in Blender with Python. Use
  when the user wants to import BVH or FBX mocap data, retarget motion to
  armatures, track camera or object motion from video, solve camera motion,
  clean up motion capture data, or script any tracking pipeline in Blender.
license: Apache-2.0
compatibility: >-
  Requires Blender 3.0+. Video tracking needs ffmpeg (bundled).
  Run: blender --background --python script.py
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: automation
  tags: ["blender", "motion-capture", "tracking", "mocap", "animation"]
---

# Blender Motion Capture

## Overview

Import, process, and retarget motion capture data in Blender using Python. Work with BVH/FBX mocap files, track camera and object motion from video footage, solve 3D camera paths, and clean up animation data — all scriptable from the terminal.

## Instructions

### 1. Import BVH motion capture files

```python
import bpy

# Import BVH file
bpy.ops.import_anim.bvh(
    filepath="/path/to/mocap.bvh",
    filter_glob="*.bvh",
    target='ARMATURE',          # ARMATURE or OBJECT
    global_scale=1.0,
    frame_start=1,
    use_fps_scale=False,        # scale keyframes to match scene FPS
    use_cyclic=False,
    rotate_mode='NATIVE',       # QUATERNION, NATIVE, XYZ, XZY, YXZ, YZX, ZXY, ZYX
    axis_forward='-Z',
    axis_up='Y'
)

armature = bpy.context.active_object
print(f"Imported: {armature.name}")
print(f"Bones: {len(armature.data.bones)}")

# Check animation data
action = armature.animation_data.action
print(f"Action: {action.name}")
print(f"Frame range: {action.frame_range}")
```

### 2. Import FBX with animation

```python
import bpy

bpy.ops.import_scene.fbx(
    filepath="/path/to/mocap.fbx",
    use_anim=True,
    anim_offset=1.0,
    ignore_leaf_bones=True,         # skip end bones
    force_connect_children=False,
    automatic_bone_orientation=True,
    primary_bone_axis='Y',
    secondary_bone_axis='X'
)

# The imported armature is selected
armature = bpy.context.active_object
if armature and armature.type == 'ARMATURE':
    action = armature.animation_data.action
    print(f"Bones: {len(armature.data.bones)}")
    print(f"Action frames: {int(action.frame_range[0])}-{int(action.frame_range[1])}")
```

### 3. Retarget motion between armatures

```python
import bpy
from mathutils import Matrix

def retarget_motion(source_armature, target_armature, bone_mapping):
    """
    Retarget animation from source to target using a bone name mapping.
    bone_mapping: dict of {target_bone_name: source_bone_name}
    """
    source_action = source_armature.animation_data.action
    frame_start = int(source_action.frame_range[0])
    frame_end = int(source_action.frame_range[1])

    # Ensure target has animation data
    if not target_armature.animation_data:
        target_armature.animation_data_create()
    new_action = bpy.data.actions.new(f"{source_action.name}_retarget")
    target_armature.animation_data.action = new_action

    scene = bpy.context.scene

    for frame in range(frame_start, frame_end + 1):
        scene.frame_set(frame)

        for target_bone_name, source_bone_name in bone_mapping.items():
            if source_bone_name not in source_armature.pose.bones:
                continue
            if target_bone_name not in target_armature.pose.bones:
                continue

            src_bone = source_armature.pose.bones[source_bone_name]
            tgt_bone = target_armature.pose.bones[target_bone_name]

            # Copy rotation
            tgt_bone.rotation_quaternion = src_bone.rotation_quaternion
            tgt_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)

            # Copy location for root bone only
            if source_bone_name == list(bone_mapping.values())[0]:
                tgt_bone.location = src_bone.location
                tgt_bone.keyframe_insert(data_path="location", frame=frame)

    print(f"Retargeted {len(bone_mapping)} bones, frames {frame_start}-{frame_end}")

# Example bone mapping (Mixamo → Rigify)
mapping = {
    "spine": "mixamorig:Hips",
    "spine.001": "mixamorig:Spine",
    "spine.002": "mixamorig:Spine1",
    "spine.003": "mixamorig:Spine2",
    "spine.004": "mixamorig:Neck",
    "spine.006": "mixamorig:Head",
    "upper_arm.L": "mixamorig:LeftArm",
    "forearm.L": "mixamorig:LeftForeArm",
    "hand.L": "mixamorig:LeftHand",
    "upper_arm.R": "mixamorig:RightArm",
    "forearm.R": "mixamorig:RightForeArm",
    "hand.R": "mixamorig:RightHand",
    "thigh.L": "mixamorig:LeftUpLeg",
    "shin.L": "mixamorig:LeftLeg",
    "foot.L": "mixamorig:LeftFoot",
    "thigh.R": "mixamorig:RightUpLeg",
    "shin.R": "mixamorig:RightLeg",
    "foot.R": "mixamorig:RightFoot",
}
```

### 4. Clean up motion capture data

```python
import bpy

armature = bpy.context.active_object
action = armature.animation_data.action

# Remove jitter with F-Curve smoothing
for fcurve in action.fcurves:
    # Add a Smooth modifier
    mod = fcurve.modifiers.new(type='NOISE')
    mod.strength = 0.0  # remove — just showing structure

    # Decimate keyframes (reduce count while keeping shape)
    # Select all keyframes first
    for kp in fcurve.keyframe_points:
        kp.select_control_point = True

# Use Blender's built-in decimate operator
bpy.context.view_layer.objects.active = armature
bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.select_all(action='SELECT')

# Decimate keyframes (requires pose mode context)
# Alternative: manual decimation
def decimate_fcurve(fcurve, factor=0.5):
    """Remove every Nth keyframe to reduce data."""
    points = fcurve.keyframe_points
    total = len(points)
    keep_every = max(1, int(1.0 / factor))
    remove_indices = [i for i in range(total) if i % keep_every != 0 and i != 0 and i != total - 1]
    for i in reversed(remove_indices):
        points.remove(points[i])

for fcurve in action.fcurves:
    decimate_fcurve(fcurve, factor=0.5)
    fcurve.update()

print(f"Cleaned {len(action.fcurves)} F-Curves")
```

### 5. Set up video motion tracking

```python
import bpy

# Create a new movie clip
clip = bpy.data.movieclips.load("/path/to/footage.mp4")

# Set up tracking scene
scene = bpy.context.scene
scene.active_clip = clip

# Configure tracking settings
tracking = clip.tracking
settings = tracking.settings
settings.default_pattern_size = 21
settings.default_search_size = 71
settings.default_motion_model = 'AFFINE'  # TRANSLATION, AFFINE, PERSPECTIVE
settings.use_default_brute = True
settings.use_default_normalization = True

# Camera settings for solving
camera = tracking.camera
camera.sensor_width = 36.0        # full-frame sensor mm
camera.focal_length = 50.0        # lens mm
camera.pixel_aspect = 1.0
camera.units = 'MILLIMETERS'

# Add tracking markers programmatically
track = tracking.tracks.new(name="Marker_01", frame=1)
# Set marker position (normalized 0-1 coords, center = 0.5, 0.5)
marker = track.markers[0]
marker.co = (0.5, 0.5)

print(f"Clip: {clip.name}")
print(f"Resolution: {clip.size[0]}x{clip.size[1]}")
print(f"Frames: {clip.frame_duration}")
```

### 6. Solve camera motion

```python
import bpy

clip = bpy.context.scene.active_clip

# Track markers across frames (operator-based, needs context)
# In background mode, set up markers and solve:

# Configure solver
tracking = clip.tracking
settings = tracking.settings
settings.use_tripod_solver = False    # True for locked-off tripod shots
settings.refine_intrinsics = 'FOCAL_LENGTH'  # NONE, FOCAL_LENGTH, FOCAL_LENGTH_RADIAL_K1, etc.

# Solve camera motion
bpy.ops.clip.solve_camera()

# Check solve error
solve_error = tracking.reconstruction.average_error
print(f"Solve error: {solve_error:.4f} px")

if solve_error < 0.5:
    print("Good solve!")
elif solve_error < 1.0:
    print("Acceptable solve — may need refinement")
else:
    print("Poor solve — add more markers or adjust settings")

# Set up scene from solved data
bpy.ops.clip.setup_tracking_scene()
```

### 7. Apply tracked motion to objects

```python
import bpy

# After solving, apply camera motion to scene camera
clip = bpy.context.scene.active_clip
tracking = clip.tracking

# Create camera from tracking data
scene = bpy.context.scene
scene.active_clip = clip

# Constraint-based approach: Object follows track
obj = bpy.data.objects["MyObject"]
constraint = obj.constraints.new(type='FOLLOW_TRACK')
constraint.clip = clip
constraint.track = tracking.tracks["Marker_01"]
constraint.use_3d_position = True
constraint.camera = scene.camera

# Bake constraint to keyframes
bpy.context.view_layer.objects.active = obj
bpy.ops.object.select_all(action='DESELECT')
obj.select_set(True)

scene.frame_start = 1
scene.frame_end = clip.frame_duration

# Bake the constraint animation
bpy.ops.nla.bake(
    frame_start=scene.frame_start,
    frame_end=scene.frame_end,
    only_selected=True,
    visual_keying=True,
    clear_constraints=True,
    bake_types={'OBJECT'}
)

print(f"Baked tracking data to {obj.name}")
```

### 8. Export animation data

```python
import bpy

armature = bpy.context.active_object
action = armature.animation_data.action

# Export as BVH
bpy.ops.export_anim.bvh(
    filepath="/tmp/output_mocap.bvh",
    global_scale=1.0,
    frame_start=int(action.frame_range[0]),
    frame_end=int(action.frame_range[1]),
    rotate_mode='NATIVE',
    root_transform_only=False
)

# Export as FBX with animation
bpy.ops.export_scene.fbx(
    filepath="/tmp/output_anim.fbx",
    use_selection=True,
    bake_anim=True,
    bake_anim_use_all_bones=True,
    bake_anim_use_nla_strips=False,
    bake_anim_use_all_actions=False,
    bake_anim_simplify_factor=1.0,
    add_leaf_bones=False
)

print("Animation exported.")
```

## Examples

### Example 1: Batch import and preview mocap library

**User request:** "Import all BVH files from a folder, list their bone counts and frame ranges"

```python
import bpy
import glob
import os

mocap_dir = "/path/to/mocap_library/"
bvh_files = sorted(glob.glob(os.path.join(mocap_dir, "*.bvh")))

print(f"=== Mocap Library Report ===")
print(f"Found {len(bvh_files)} BVH files\n")

for filepath in bvh_files:
    # Clear scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Import
    bpy.ops.import_anim.bvh(
        filepath=filepath,
        target='ARMATURE',
        global_scale=0.01,
        frame_start=1
    )

    armature = bpy.context.active_object
    if armature and armature.animation_data:
        action = armature.animation_data.action
        frame_range = action.frame_range
        duration = (frame_range[1] - frame_range[0]) / bpy.context.scene.render.fps

        print(f"{os.path.basename(filepath)}:")
        print(f"  Bones: {len(armature.data.bones)}")
        print(f"  Frames: {int(frame_range[0])}-{int(frame_range[1])}")
        print(f"  Duration: {duration:.1f}s")
        print(f"  Bone names: {', '.join(b.name for b in list(armature.data.bones)[:5])}...")
    else:
        print(f"{os.path.basename(filepath)}: FAILED TO IMPORT")
    print()
```

Run: `blender --background --python scan_mocap.py`

### Example 2: Apply mocap to a character and render

**User request:** "Import a BVH file, apply it to my rigged character, and render a preview"

```python
import bpy
import math

# Open the character file
bpy.ops.wm.open_mainfile(filepath="/path/to/character.blend")

# The character armature should be named
char_armature = bpy.data.objects["Armature"]

# Import the BVH mocap
bpy.ops.import_anim.bvh(
    filepath="/path/to/walk_cycle.bvh",
    target='ARMATURE',
    global_scale=0.01,
    frame_start=1
)
mocap_armature = bpy.context.active_object

# Simple copy: transfer action directly (if bone names match)
mocap_action = mocap_armature.animation_data.action

# Apply action to character
if not char_armature.animation_data:
    char_armature.animation_data_create()
char_armature.animation_data.action = mocap_action

# Remove the mocap armature (we only needed its action)
bpy.ops.object.select_all(action='DESELECT')
mocap_armature.select_set(True)
bpy.ops.object.delete()

# Set frame range
frame_range = mocap_action.frame_range
scene = bpy.context.scene
scene.frame_start = int(frame_range[0])
scene.frame_end = int(frame_range[1])

# Set up camera
bpy.ops.object.camera_add(location=(5, -5, 2))
cam = bpy.context.active_object
track = cam.constraints.new(type='TRACK_TO')
track.target = char_armature
scene.camera = cam

# Render preview
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.filepath = "/tmp/mocap_preview/frame_"
scene.render.image_settings.file_format = 'PNG'

bpy.ops.render.render(animation=True)
print("Preview rendered.")
```

## Guidelines

- BVH is the simplest mocap format — plain text with hierarchy and motion data. Use it for compatibility. FBX supports richer data (blend shapes, multiple takes) but is more complex.
- Scale matters: BVH files often use centimeters while Blender defaults to meters. Set `global_scale=0.01` when importing cm-based BVH files.
- Bone name matching is critical for retargeting. Common conventions: Mixamo uses `mixamorig:BoneName`, BVH varies by source. Build a mapping dictionary for each source format.
- For retargeting, copy rotations for all bones but only copy location for the root/hip bone. Copying location on all bones breaks the skeleton.
- Clean up imported mocap by decimating keyframes — raw mocap often has a keyframe on every frame, which makes manual editing difficult.
- Camera solve quality depends on marker count and distribution. Use 8+ well-distributed markers. Keep solve error below 0.5px for good results.
- Use `bpy.ops.nla.bake()` to convert constraints (Follow Track, Copy Rotation) to keyframes for export or further editing.
- Motion tracking operators (`clip.solve_camera`, `clip.track_markers`) require specific editor context and may not work in pure background mode. Set up markers in background mode, then solve interactively or via a workaround context override.
- Always export animations with `bake_anim=True` in FBX to flatten NLA strips and constraints into keyframes that other software can read.
