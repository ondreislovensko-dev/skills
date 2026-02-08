---
name: blender-addon-dev
description: >-
  Build custom Blender add-ons with Python. Use when the user wants to create
  a Blender add-on, register operators, build UI panels, add custom properties,
  create menus, package an add-on for distribution, or extend Blender with
  custom tools and workflows.
license: Apache-2.0
compatibility: >-
  Requires Blender 3.0+. Add-ons are standard Python modules.
  Test: blender --background --python addon.py
metadata:
  author: terminal-skills
  version: "1.0.0"
  category: development
  tags: ["blender", "addon", "plugin", "operators", "ui-panels"]
---

# Blender Add-on Development

## Overview

Create custom Blender add-ons that extend the application with new operators, UI panels, properties, and menus. Add-ons are Python modules that register with Blender's internal system and can be installed, enabled, and shared like any Blender extension.

## Instructions

### 1. Add-on structure and bl_info

```python
bl_info = {
    "name": "My Custom Add-on",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),       # minimum Blender version
    "location": "View3D > Sidebar > My Tab",
    "description": "A short description of what the add-on does",
    "category": "Object",       # 3D View, Object, Mesh, Add Mesh, Rigging, Animation, etc.
    "doc_url": "",
    "tracker_url": "",
}

import bpy

# ... classes defined here ...

def register():
    """Called when the add-on is enabled."""
    pass

def unregister():
    """Called when the add-on is disabled."""
    pass

if __name__ == "__main__":
    register()
```

The `if __name__ == "__main__"` block allows testing by running the script directly in Blender's text editor or via `--python`.

### 2. Create a custom operator

```python
import bpy

class OBJECT_OT_my_operator(bpy.types.Operator):
    """Tooltip shown on hover"""
    bl_idname = "object.my_operator"      # unique identifier
    bl_label = "My Operator"              # display name
    bl_options = {'REGISTER', 'UNDO'}     # enable undo support

    # Operator properties (shown in the redo panel)
    scale_factor: bpy.props.FloatProperty(
        name="Scale",
        description="Scale factor to apply",
        default=2.0,
        min=0.1,
        max=100.0
    )
    axis: bpy.props.EnumProperty(
        name="Axis",
        items=[
            ('X', "X Axis", "Scale on X"),
            ('Y', "Y Axis", "Scale on Y"),
            ('Z', "Z Axis", "Scale on Z"),
            ('ALL', "All Axes", "Scale uniformly"),
        ],
        default='ALL'
    )

    @classmethod
    def poll(cls, context):
        """Only enable when an object is selected."""
        return context.active_object is not None

    def execute(self, context):
        """Run the operator logic."""
        obj = context.active_object
        s = self.scale_factor
        if self.axis == 'ALL':
            obj.scale *= s
        elif self.axis == 'X':
            obj.scale.x *= s
        elif self.axis == 'Y':
            obj.scale.y *= s
        elif self.axis == 'Z':
            obj.scale.z *= s

        self.report({'INFO'}, f"Scaled {obj.name} by {s}")
        return {'FINISHED'}

    def invoke(self, context, event):
        """Called when operator is triggered. Show dialog for user input."""
        return context.window_manager.invoke_props_dialog(self)


def register():
    bpy.utils.register_class(OBJECT_OT_my_operator)

def unregister():
    bpy.utils.unregister_class(OBJECT_OT_my_operator)
```

Naming convention: `CATEGORY_OT_name` for operators. Categories: `OBJECT`, `MESH`, `VIEW3D`, `SCENE`, etc.

### 3. Create a UI panel

```python
import bpy

class VIEW3D_PT_my_panel(bpy.types.Panel):
    bl_label = "My Tools"
    bl_idname = "VIEW3D_PT_my_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "My Tab"          # sidebar tab name
    bl_context = "objectmode"       # only show in object mode

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        # Operator button
        layout.operator("object.my_operator", text="Scale Object", icon='FULLSCREEN_ENTER')

        # Properties
        if obj:
            layout.label(text=f"Active: {obj.name}", icon='OBJECT_DATA')
            layout.prop(obj, "location")
            layout.prop(obj, "scale")

            # Custom layout
            row = layout.row(align=True)
            row.prop(obj, "show_name", text="Name")
            row.prop(obj, "show_axis", text="Axis")

            # Box section
            box = layout.box()
            box.label(text="Transform", icon='ORIENTATION_GLOBAL')
            col = box.column(align=True)
            col.prop(obj, "location", index=0, text="X")
            col.prop(obj, "location", index=1, text="Y")
            col.prop(obj, "location", index=2, text="Z")


def register():
    bpy.utils.register_class(VIEW3D_PT_my_panel)

def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_my_panel)
```

Panel spaces: `VIEW_3D`, `PROPERTIES`, `IMAGE_EDITOR`, `NODE_EDITOR`, `SEQUENCE_EDITOR`.
Region types: `UI` (sidebar), `TOOLS` (toolbar), `HEADER`, `WINDOW`.

### 4. Add custom properties

```python
import bpy

class MySettings(bpy.types.PropertyGroup):
    my_bool: bpy.props.BoolProperty(
        name="Enable Feature",
        default=False
    )
    my_int: bpy.props.IntProperty(
        name="Count",
        default=5,
        min=1,
        max=100
    )
    my_float: bpy.props.FloatProperty(
        name="Factor",
        default=1.0,
        min=0.0,
        max=10.0,
        step=10,             # UI step (value * 0.01)
        precision=2
    )
    my_string: bpy.props.StringProperty(
        name="Label",
        default="",
        maxlen=256
    )
    my_enum: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ('OPT_A', "Option A", "First option"),
            ('OPT_B', "Option B", "Second option"),
            ('OPT_C', "Option C", "Third option"),
        ],
        default='OPT_A'
    )
    my_color: bpy.props.FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=4,
        default=(1.0, 0.5, 0.0, 1.0),
        min=0.0,
        max=1.0
    )
    my_path: bpy.props.StringProperty(
        name="File Path",
        subtype='FILE_PATH'
    )

def register():
    bpy.utils.register_class(MySettings)
    bpy.types.Scene.my_settings = bpy.props.PointerProperty(type=MySettings)

def unregister():
    del bpy.types.Scene.my_settings
    bpy.utils.unregister_class(MySettings)
```

Access in panels: `context.scene.my_settings.my_bool`. Property types: `BoolProperty`, `IntProperty`, `FloatProperty`, `StringProperty`, `EnumProperty`, `FloatVectorProperty`, `IntVectorProperty`, `PointerProperty`, `CollectionProperty`.

### 5. Add menu entries

```python
import bpy

class OBJECT_MT_my_menu(bpy.types.Menu):
    bl_label = "My Custom Menu"
    bl_idname = "OBJECT_MT_my_menu"

    def draw(self, context):
        layout = self.layout
        layout.operator("object.my_operator", text="Scale Up")
        layout.separator()
        layout.operator("mesh.primitive_cube_add", text="Add Cube")

def draw_menu_item(self, context):
    """Append to an existing menu."""
    self.layout.separator()
    self.layout.operator("object.my_operator", text="My Scale Tool")

def draw_context_menu(self, context):
    """Add to right-click context menu."""
    self.layout.separator()
    self.layout.operator("object.my_operator")

def register():
    bpy.utils.register_class(OBJECT_MT_my_menu)
    # Append to Object menu in 3D viewport header
    bpy.types.VIEW3D_MT_object.append(draw_menu_item)
    # Append to right-click context menu
    bpy.types.VIEW3D_MT_object_context_menu.append(draw_context_menu)

def unregister():
    bpy.types.VIEW3D_MT_object_context_menu.remove(draw_context_menu)
    bpy.types.VIEW3D_MT_object.remove(draw_menu_item)
    bpy.utils.unregister_class(OBJECT_MT_my_menu)
```

### 6. Add keymaps

```python
import bpy

addon_keymaps = []

def register():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='Object Mode', space_type='EMPTY')
        kmi = km.keymap_items.new(
            "object.my_operator",
            type='T',
            value='PRESS',
            ctrl=True,
            shift=True
        )
        kmi.properties.scale_factor = 2.0
        addon_keymaps.append((km, kmi))

def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
```

### 7. Package for distribution

```
my_addon/
├── __init__.py          # bl_info + register/unregister + imports
├── operators.py         # operator classes
├── panels.py            # UI panel classes
├── properties.py        # property group classes
└── utils.py             # helper functions
```

**`__init__.py`:**
```python
bl_info = {
    "name": "My Add-on",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "description": "My add-on description",
    "category": "Object",
}

from . import operators, panels, properties

classes = (
    properties.MySettings,
    operators.OBJECT_OT_my_operator,
    panels.VIEW3D_PT_my_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.my_settings = bpy.props.PointerProperty(type=properties.MySettings)

def unregister():
    del bpy.types.Scene.my_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
```

Zip the folder and install via Edit > Preferences > Add-ons > Install.

## Examples

### Example 1: Quick export add-on

**User request:** "Create an add-on with a panel button that exports selected objects as FBX"

```python
bl_info = {
    "name": "Quick FBX Export",
    "author": "Example",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Export",
    "description": "One-click FBX export for selected objects",
    "category": "Import-Export",
}

import bpy
import os

class EXPORT_OT_quick_fbx(bpy.types.Operator):
    bl_idname = "export.quick_fbx"
    bl_label = "Quick FBX Export"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    def execute(self, context):
        settings = context.scene.quick_fbx
        output_dir = bpy.path.abspath(settings.export_path)
        os.makedirs(output_dir, exist_ok=True)

        for obj in context.selected_objects:
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            context.view_layer.objects.active = obj
            filepath = os.path.join(output_dir, f"{obj.name}.fbx")
            bpy.ops.export_scene.fbx(
                filepath=filepath,
                use_selection=True,
                apply_scale_options='FBX_SCALE_ALL'
            )
            self.report({'INFO'}, f"Exported: {filepath}")

        self.report({'INFO'}, f"Exported {len(context.selected_objects)} objects")
        return {'FINISHED'}

class QuickFBXSettings(bpy.types.PropertyGroup):
    export_path: bpy.props.StringProperty(
        name="Export Path",
        subtype='DIR_PATH',
        default="//exports/"
    )

class VIEW3D_PT_quick_fbx(bpy.types.Panel):
    bl_label = "Quick FBX Export"
    bl_idname = "VIEW3D_PT_quick_fbx"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Export"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.quick_fbx
        layout.prop(settings, "export_path")
        layout.operator("export.quick_fbx", icon='EXPORT')
        layout.label(text=f"Selected: {len(context.selected_objects)} objects")

classes = (QuickFBXSettings, EXPORT_OT_quick_fbx, VIEW3D_PT_quick_fbx)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.quick_fbx = bpy.props.PointerProperty(type=QuickFBXSettings)

def unregister():
    del bpy.types.Scene.quick_fbx
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
```

### Example 2: Batch rename add-on with UI

**User request:** "Create an add-on with a panel to batch rename objects with a prefix and auto-numbering"

```python
bl_info = {
    "name": "Batch Renamer",
    "author": "Example",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > Rename",
    "description": "Batch rename selected objects with prefix and numbering",
    "category": "Object",
}

import bpy

class RenameSettings(bpy.types.PropertyGroup):
    prefix: bpy.props.StringProperty(name="Prefix", default="obj")
    separator: bpy.props.EnumProperty(
        name="Separator",
        items=[('_', "Underscore (_)", ""), ('.', "Dot (.)", ""), ('-', "Dash (-)", "")],
        default='_'
    )
    start_number: bpy.props.IntProperty(name="Start", default=1, min=0)
    padding: bpy.props.IntProperty(name="Padding", default=3, min=1, max=6)

class OBJECT_OT_batch_rename(bpy.types.Operator):
    bl_idname = "object.batch_rename"
    bl_label = "Batch Rename"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    def execute(self, context):
        settings = context.scene.rename_settings
        objects = sorted(context.selected_objects, key=lambda o: o.name)

        for i, obj in enumerate(objects):
            num = settings.start_number + i
            obj.name = f"{settings.prefix}{settings.separator}{str(num).zfill(settings.padding)}"

        self.report({'INFO'}, f"Renamed {len(objects)} objects")
        return {'FINISHED'}

class VIEW3D_PT_batch_rename(bpy.types.Panel):
    bl_label = "Batch Rename"
    bl_idname = "VIEW3D_PT_batch_rename"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Rename"

    def draw(self, context):
        layout = self.layout
        settings = context.scene.rename_settings

        layout.prop(settings, "prefix")
        layout.prop(settings, "separator")
        row = layout.row(align=True)
        row.prop(settings, "start_number")
        row.prop(settings, "padding")

        preview = f"{settings.prefix}{settings.separator}{'1'.zfill(settings.padding)}"
        layout.label(text=f"Preview: {preview}", icon='INFO')
        layout.operator("object.batch_rename", icon='SORTALPHA')

classes = (RenameSettings, OBJECT_OT_batch_rename, VIEW3D_PT_batch_rename)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.rename_settings = bpy.props.PointerProperty(type=RenameSettings)

def unregister():
    del bpy.types.Scene.rename_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
```

## Guidelines

- Follow the naming convention strictly: `CATEGORY_OT_name` for operators, `CATEGORY_PT_name` for panels, `CATEGORY_MT_name` for menus. Blender enforces this.
- Register classes in dependency order: PropertyGroups first, then Operators, then Panels. Unregister in reverse.
- Always implement `poll()` on operators to prevent errors when context is wrong (e.g., no object selected).
- Use `{'REGISTER', 'UNDO'}` in `bl_options` for operators that modify scene data — this enables Ctrl+Z.
- Clean up everything in `unregister()`: delete custom properties from types, remove menu entries, clear keymaps. Incomplete cleanup causes errors on disable/re-enable.
- Use `bpy.path.abspath()` to resolve `//` relative paths in file path properties.
- For multi-file add-ons, put `bl_info` only in `__init__.py`. Import submodules and register all classes from there.
- Test with `blender --background --python addon.py` for registration errors. Test UI interactively by running the script in Blender's text editor.
- Add-ons stored in `~/.config/blender/<version>/scripts/addons/` (Linux) or `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons\` (Windows) are auto-discovered.
- Use `self.report({'INFO'}, "message")` in operators to show status in Blender's status bar.
